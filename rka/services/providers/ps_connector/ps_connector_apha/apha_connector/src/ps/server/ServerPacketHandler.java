// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ServerPacketHandler.java

package ps.server;

import java.io.IOException;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.Properties;

import ps.net.AddUserContent;
import ps.net.ChangePasswordContent;
import ps.net.ChangeUserRightContent;
import ps.net.ChatContent;
import ps.net.ClientInfoContent;
import ps.net.ClientListContent;
import ps.net.DpsParseContent;
import ps.net.LoginContent;
import ps.net.MessageContent;
import ps.net.Packet;
import ps.net.RemoveUserContent;
import ps.net.ServerCmdContent;
import ps.net.TriggerDescContent;
import ps.net.TriggerEventContent;
import ps.server.net.ClientInfo;
import ps.server.net.PacketSender;
import ps.server.net.PsServerSocket;
import ps.server.rights.RightsManager;
import ps.server.rights.User;
import ps.server.trigger.TriggerEntry;
import ps.server.trigger.TriggerManager;
import ps.util.MD5;

// Referenced classes of package ps.server:
//            ClientManager, DelayedLookup

public class ServerPacketHandler extends Thread {

	public ServerPacketHandler(Properties serverProps) throws IOException {
		super("ServerPacketHandler");
		running = true;
		rightsManager = new RightsManager();
		triggerManager = new TriggerManager();
		clientManager = new ClientManager();
		packetSender = new PacketSender();
		recievdPackets = new LinkedList();
		sentChatPackets = new LinkedList();
		lastClientInfoSent = 0L;
		clientListChanged = false;
		clientInfoLookup = new DelayedLookup(100) {

			@Override
			protected void lookupNow() {
				ClientInfo aclientinfo[];
				int k = (aclientinfo = clientManager.getAllClientInfos()).length;
				for (int j = 0; j < k; j++) {
					ClientInfo clientInfo = aclientinfo[j];
					long currentTime = System.currentTimeMillis();
					long lastRecievedMsg = clientInfo.getLastRecievedMsgTime();
					if (currentTime - lastRecievedMsg > 30000L)
						fireClientConectionLost(clientInfo);
					else
						clientInfo.setLinkDead(currentTime - lastRecievedMsg > 10000L);
				}

				ClientListContent clientListContent = null;
				if (clientListChanged) {
					clientListChanged = false;
					lastSendClientInfos = clientManager.getClientInfosSortedByUserName();
					String clientNames[] = new String[lastSendClientInfos.length];
					for (int i = 0; i < lastSendClientInfos.length; i++)
						clientNames[i] = lastSendClientInfos[i].getUser().getName();

					clientListContent = new ClientListContent(clientNames);
				}
				ClientInfo aclientinfo1[];
				int i1 = (aclientinfo1 = lastSendClientInfos).length;
				for (int l = 0; l < i1; l++) {
					ClientInfo currentClientInfo = aclientinfo1[l];
					Packet packet;
					if (clientListContent != null) {
						packet = new Packet(6);
						packet.setReciever(currentClientInfo);
						packet.setContent(clientListContent);
						packetSender.send(packet);
					}
					packet = new Packet(12);
					packet.setContent(new ClientInfoContent(lastSendClientInfos));
					packet.setReciever(currentClientInfo);
					packetSender.send(packet);
					try {
						Thread.sleep(3000 / lastSendClientInfos.length);
					} catch (Exception ex) {
						ex.printStackTrace();
					}
				}

				packetSender.waitForEmptyQueue();
			}

			private ClientInfo lastSendClientInfos[];

			{
				lastSendClientInfos = new ClientInfo[0];
			}
		};
		port = 53729;
		chatChannel = null;
		try {
			port = Integer.parseInt(serverProps.getProperty("Port", "53729").trim());
			System.out.println((new StringBuilder("PORT: ")).append(port).toString());
		} catch (Exception ex) {
			System.out.println((new StringBuilder("PORT: ")).append(ex.getMessage()).toString());
			System.out.println(
					(new StringBuilder("PORT: Default Port ")).append(port).append(" wird verwendet.").toString());
		}
		chatChannel = serverProps.getProperty("ChatChannel", "").trim();
		chatChannel = chatChannel.length() != 0 ? chatChannel : null;
		System.out.println((new StringBuilder("CHAT CHANNEL: ")).append(chatChannel != null ? chatChannel : "<keiner>")
				.toString());
		psServerSocket = new PsServerSocket(this);
		psServerSocket.open(port);
		Thread lossThread = new Thread(clientInfoLookup, "LossLookupThread");
		lossThread.setDaemon(true);
		lossThread.start();
		start();
	}

	public void shutdown() {
		packetSender.stopPacketSender();
		psServerSocket.close();
	}

	public void addRecievedPacket(Packet packet) {
		synchronized (recievdPackets) {
			recievdPackets.add(packet);
		}
	}

	@Override
	public void run() {
		while (running)
			try {
				Packet packet = null;
				synchronized (recievdPackets) {
					packet = (Packet) recievdPackets.poll();
				}
				if (packet != null) {
					ClientInfo clientInfo = packet.getSender();
					User user = clientInfo.getUser();
					if (!clientInfo.isLogedIn() && packet.isTypeOf(3)) {
						LoginContent loginContent = (LoginContent) packet.getContent();
						user = rightsManager.getUserWithAuthId(new MD5(loginContent.getAuthId()));
						if (user != null) {
							ClientInfo oldClientInfo = clientManager.getClientInfoByUserName(user.getName());
							if (oldClientInfo != null) {
								Packet logoutPacket = new Packet(4);
								logoutPacket.setReciever(oldClientInfo);
								packetSender.send(logoutPacket);
								packetSender.waitForEmptyQueue();
								clientManager.removeClientInfo(oldClientInfo);
							}
							clientInfo.setUser(user);
							System.out.println(
									(new StringBuilder("LOGIN REQUEST FROM: ")).append(user.getName()).toString());
							if (loginContent.getVersion() <= 10015) {
								clientInfo.setLogedIn(true);
								sendClientListTo(clientInfo);
								clientListChanged = true;
								sendServerMessage((new StringBuilder(String.valueOf(clientInfo.getUser().getName())))
										.append(" hat sich verbunden.").toString());
								if (loginContent.getVersion() != 10015) {
									System.out.println((new StringBuilder("VERSION=10015 getVersion="))
											.append(loginContent.getVersion()).toString());
									sendServerMessageTo(clientInfo,
											"Client-Programmversion ist zu alt. Ein Update wird durchgef\374hrt!");
									sendServerCmdTo(clientInfo, 9);
								}
								sendServerCmdTo(clientInfo, user.isAdmin() ? 1 : 2);
								if (chatChannel != null)
									sendServerCmdTo(clientInfo, 12, chatChannel);
								sendTriggerDescTo(clientInfo, triggerManager.getAllTrigger());
							} else if (loginContent.getVersion() < 10015) {
								sendServerMessageTo(clientInfo,
										"Client-Programmversion ist zu alt. Ein Update wird durchgef\374hrt!");
								clientInfo.setLogedIn(true);
								sendClientListTo(clientInfo);
								clientListChanged = true;
							} else if (loginContent.getVersion() > 10015) {
								sendServerMessageTo(clientInfo,
										"Client-Programmversion ist zu neu. Bitte an Szik/Hakai wenden!");
								sendLogoutTo(clientInfo);
							}
						} else {
							clientManager.removeClientInfo(clientInfo);
							System.out.println("LOGIN REQUEST FROM: <unknown>");
						}
					}
					if (clientInfo.isLogedIn())
						label0: switch (packet.getType()) {
						case 3: // '\003'
						case 5: // '\005'
						case 6: // '\006'
						case 12: // '\f'
						default:
							break;

						case 4: // '\004'
						{
							fireClientLogedOut(clientInfo);
							clientListChanged = true;
							break;
						}

						case 2: // '\002'
						{
							clientInfo.setPing((int) (System.currentTimeMillis() - clientInfo.getLastClientInfoSent()));
							break;
						}

						case 13: // '\r'
						{
							ChatContent chatContent = (ChatContent) packet.getContent();
							if (chatContent.getReciever().equals("")) {
								chatContent.setSender(user.getName());
								sendChatMessage(chatContent);
								break;
							}
							if (chatChannel == null || !chatContent.getReciever().equalsIgnoreCase(chatChannel))
								break;
							Iterator iterator = sentChatPackets.iterator();
							boolean chatAllreadySend = false;
							while (iterator.hasNext()) {
								Packet p = (Packet) iterator.next();
								if (p.getTime() + 5000L < packet.getTime()) {
									iterator.remove();
									continue;
								}
								ChatContent c = (ChatContent) p.getContent();
								if (!c.getSender().equals(chatContent.getSender())
										|| !c.getMsg().equals(chatContent.getMsg()))
									continue;
								chatAllreadySend = true;
								break;
							}
							if (!chatAllreadySend) {
								sentChatPackets.add(packet);
								sendChatMessage(chatContent);
							}
							break;
						}

						case 7: // '\007'
						{
							if (!user.isAdmin())
								break;
							AddUserContent addUserContent = (AddUserContent) packet.getContent();
							User newUser = new User(addUserContent.getUserName(), new MD5(addUserContent.getAuthId()));
							if (rightsManager.existsUserName(newUser.getName())) {
								sendServerMessageTo(clientInfo, "Benutzername existiert bereits.");
							} else {
								rightsManager.addUser(newUser);
								sendServerMessageTo(clientInfo, (new StringBuilder("Benutzer "))
										.append(newUser.getName()).append(" wurde hinzugef\374gt.").toString());
							}
							break;
						}

						case 8: // '\b'
						{
							if (!user.isAdmin())
								break;
							RemoveUserContent removeUserContent = (RemoveUserContent) packet.getContent();
							if (rightsManager.existsUserName(removeUserContent.getUserName())) {
								rightsManager.removeUser(removeUserContent.getUserName());
								sendServerMessageTo(clientInfo, (new StringBuilder("Benutzer "))
										.append(removeUserContent.getUserName()).append(" wurde entfernt.").toString());
							} else {
								sendServerMessageTo(clientInfo, (new StringBuilder("Benutzer "))
										.append(removeUserContent.getUserName()).append(" ist unbekannt.").toString());
							}
							ClientInfo clientInfoToRemove = clientManager
									.getClientInfoByUserName(removeUserContent.getUserName());
							if (clientInfoToRemove != null)
								fireClientWasKicked(clientInfoToRemove);
							break;
						}

						case 9: // '\t'
						{
							ChangePasswordContent changePwdCont = (ChangePasswordContent) packet.getContent();
							if (!user.isAdmin() && !user.getName().equals(changePwdCont.getUserName()))
								break;
							User userToChange = rightsManager.getUserByName(changePwdCont.getUserName());
							if (userToChange != null) {
								userToChange.setAuthId(new MD5(changePwdCont.getAuthId()));
								rightsManager.save();
								sendServerMessageTo(clientInfo, (new StringBuilder("Das Passwort von "))
										.append(changePwdCont.getUserName()).append(" wurde ge\344ndert.").toString());
							} else {
								sendServerMessageTo(clientInfo, (new StringBuilder("Benutzer "))
										.append(changePwdCont.getUserName()).append(" ist unbekannt.").toString());
							}
							break;
						}

						case 10: // '\n'
						{
							if (!user.isAdmin())
								break;
							ChangeUserRightContent changeUserRightCont = (ChangeUserRightContent) packet.getContent();
							User userToChange = rightsManager.getUserByName(changeUserRightCont.getUserName());
							if (userToChange != null) {
								ClientInfo cInfoOfChangedUser = clientManager
										.getClientInfoByUserName(userToChange.getName());
								userToChange.setRight(changeUserRightCont.getRight());
								rightsManager.save();
								if (changeUserRightCont.getRight() == 1) {
									sendServerMessageTo(clientInfo,
											(new StringBuilder("Die Administrationsrechte wurden dem Benutzer "))
													.append(changeUserRightCont.getUserName())
													.append(" hinzugef\374gt.").toString());
									if (cInfoOfChangedUser != null) {
										sendServerCmdTo(cInfoOfChangedUser, 1);
										sendServerMessageTo(cInfoOfChangedUser,
												(new StringBuilder("Die Administrationsrechte wurden dem Benutzer "))
														.append(changeUserRightCont.getUserName())
														.append(" hinzugef\374gt.").toString());
									}
									break;
								}
								sendServerMessageTo(clientInfo,
										(new StringBuilder("Die Administrationsrechte wurden dem Benutzer "))
												.append(changeUserRightCont.getUserName()).append(" entfernt.")
												.toString());
								if (cInfoOfChangedUser != null) {
									sendServerCmdTo(cInfoOfChangedUser, 2);
									sendServerMessageTo(cInfoOfChangedUser,
											(new StringBuilder("Die Administrationsrechte wurden dem Benutzer "))
													.append(changeUserRightCont.getUserName()).append(" entfernt.")
													.toString());
								}
							} else {
								sendServerMessageTo(clientInfo,
										(new StringBuilder("Benutzer ")).append(changeUserRightCont.getUserName())
												.append(" ist unbekannt.").toString());
							}
							break;
						}

						case 14: // '\016'
						{
							if (!user.isAdmin())
								break;
							TriggerDescContent triggerDesc = (TriggerDescContent) packet.getContent();
							if (triggerDesc.getCmd() == 1)
								triggerManager.addTriggers(triggerDesc.getTriggerEntries());
							else if (triggerDesc.getCmd() == 2)
								triggerManager.removeTrigger(triggerDesc.getTriggerEntry());
							sendTriggerDesc(triggerManager.getAllTrigger());
							break;
						}

						case 15: // '\017'
						{
							TriggerEventContent triggerEventContent = (TriggerEventContent) packet.getContent();
							triggerEventContent.setSender(user.getName());
							TriggerEntry entry = triggerManager.getTriggerById(triggerEventContent.getTriggerId());
							if (entry == null || !entry.isActive())
								break;
							if (entry.getQuantity() == 0) {
								sendTriggerEvent(triggerEventContent);
								break;
							}
							long currentTime = System.currentTimeMillis();
							if (currentTime - entry.getFirstTriggerTime() > entry.getIgnoreTimer() * 1000) {
								entry.setFirstTriggerTime(currentTime);
								entry.setTriggerCount(1);
								entry.clearAttrStrings();
								if (triggerEventContent.getAttrStr().length() > 0)
									entry.addAttrString(triggerEventContent.getAttrStr());
								sendTriggerEvent(triggerEventContent);
								break;
							}
							if (entry.getQuantity() <= entry.getTriggerCount())
								break;
							if (triggerEventContent.getAttrStr().length() > 0) {
								if (!entry.containsAttrString(triggerEventContent.getAttrStr())) {
									entry.addAttrString(triggerEventContent.getAttrStr());
									entry.increaseTriggerCount();
									sendTriggerEvent(triggerEventContent);
								}
							} else {
								entry.increaseTriggerCount();
								sendTriggerEvent(triggerEventContent);
							}
							break;
						}

						case 16: // '\020'
						{
							if (clientInfo.isDpsParseSharer()) {
								DpsParseContent dpsParseContent = (DpsParseContent) packet.getContent();
								sendDpsParse(dpsParseContent);
							}
							break;
						}

						case 20: // '\024'
						{
							psServerSocket.Updater(0);
							break;
						}

						case 17: // '\021'
						{
							psServerSocket.Updater(1);
							break;
						}

						case 18: // '\022'
						{
							psServerSocket.Updater(2);
							break;
						}

						case 19: // '\023'
						{
							psServerSocket.Updater(3);
							break;
						}

						case 11: // '\013'
						{
							ServerCmdContent serverCmdContent = (ServerCmdContent) packet.getContent();
							switch (serverCmdContent.getCommand()) {
							case 9: // '\t'
							case 12: // '\f'
							default:
								break label0;

							case 5: // '\005'
								clientInfo.setAfk(true);
								sendServerMessage((new StringBuilder(String.valueOf(user.getName())))
										.append(" geht AFK.").toString());
								break label0;

							case 6: // '\006'
								sendServerMessage((new StringBuilder(String.valueOf(user.getName())))
										.append(" ist zur\374ck.").toString());
								clientInfo.setAfk(false);
								break label0;

							case 7: // '\007'
								clientInfo.setLogReadActive(true);
								break label0;

							case 8: // '\b'
								clientInfo.setLogReadActive(false);
								break label0;

							case 10: // '\n'
								if (user.isAdmin())
									setDpsParseSharer(serverCmdContent.getParam1());
								break label0;

							case 11: // '\013'
								if (user.isAdmin())
									removeDpsParseSharer(serverCmdContent.getParam1());
								break label0;

							case 13: // '\r'
								break;
							}
							try {
								if (serverCmdContent.getParam1().length() > 0
										&& serverCmdContent.getParam2().length() == 0) {
									clientInfo.setGroupNumber(Integer.parseInt(serverCmdContent.getParam1()));
									break;
								}
								if (serverCmdContent.getParam1().length() > 0
										&& serverCmdContent.getParam2().length() > 0 && user.isAdmin()) {
									ClientInfo clientInfoToChange = clientManager
											.getClientInfoByUserName(serverCmdContent.getParam1());
									clientInfoToChange.setGroupNumber(Integer.parseInt(serverCmdContent.getParam2()));
								}
								break;
							} catch (Exception exception) {
							}
							break;
						}
						}
				}
				if (recievdPackets.isEmpty())
					sleep(1L);
			} catch (Exception ex) {
				ex.printStackTrace();
			}
	}

	public void fireClientLogedOut(ClientInfo clientInfo) {
		clientManager.removeClientInfo(clientInfo);
		if (clientInfo.getUser() != null)
			sendServerMessage((new StringBuilder(String.valueOf(clientInfo.getUser().getName())))
					.append(" hat sich getrennt.").toString());
		if (clientInfo.isLogedIn())
			clientListChanged = true;
	}

	public void fireClientConectionLost(ClientInfo clientInfo) {
		clientManager.removeClientInfo(clientInfo);
		if (clientInfo.getUser() != null)
			sendServerMessage((new StringBuilder(String.valueOf(clientInfo.getUser().getName())))
					.append(" hat die Verbindung verloren.").toString());
		if (clientInfo.isLogedIn())
			clientListChanged = true;
	}

	public void fireClientWasKicked(ClientInfo clientInfo) {
		clientManager.removeClientInfo(clientInfo);
		if (clientInfo.getUser() != null)
			sendServerMessage((new StringBuilder(String.valueOf(clientInfo.getUser().getName())))
					.append(" wurde gekickt.").toString());
		if (clientInfo.isLogedIn())
			clientListChanged = true;
	}

	private void sendToAll(Packet packet) {
		packet.setReciever(clientManager.getAllClientInfos());
		packetSender.send(packet);
	}

	private void sendServerMessage(String msg) {
		MessageContent msgContent = new MessageContent(msg);
		Packet packet = new Packet(5);
		packet.setContent(msgContent);
		sendToAll(packet);
	}

	private void sendChatMessage(ChatContent chatContent) {
		Packet packet = new Packet(13);
		packet.setContent(chatContent);
		sendToAll(packet);
	}

	private void sendServerMessageTo(ClientInfo clientInfo, String msg) {
		Packet packet = new Packet(5);
		packet.setContent(new MessageContent(msg));
		packet.setReciever(clientInfo);
		packetSender.send(packet);
	}

	private void sendClientListTo(ClientInfo clientInfo) {
		ClientInfo clientInfos[] = clientManager.getClientInfosSortedByUserName();
		String clientNames[] = new String[clientInfos.length];
		for (int i = 0; i < clientInfos.length; i++)
			clientNames[i] = clientInfos[i].getUser().getName();

		ClientListContent content = new ClientListContent(clientNames);
		Packet packet = new Packet(6);
		packet.setReciever(clientInfo);
		packet.setContent(content);
		packetSender.send(packet);
	}

	private void sendLogoutTo(ClientInfo clientInfo) {
		Packet packet = new Packet(4);
		packet.setReciever(clientInfo);
		packetSender.send(packet);
		packetSender.waitForEmptyQueue();
		clientManager.removeClientInfo(clientInfo);
	}

	private void sendServerCmdTo(ClientInfo clientInfo, int cmd) {
		Packet packet = new Packet(11);
		packet.setContent(new ServerCmdContent(cmd));
		packet.setReciever(clientInfo);
		packetSender.send(packet);
	}

	private void sendServerCmdTo(ClientInfo clientInfo, int cmd, String param1) {
		Packet packet = new Packet(11);
		packet.setContent(new ServerCmdContent(cmd, param1));
		packet.setReciever(clientInfo);
		packetSender.send(packet);
	}

	private void sendTriggerDesc(TriggerEntry triggers[]) {
		TriggerDescContent content = new TriggerDescContent(1, triggers);
		Packet packet = new Packet(14);
		packet.setContent(content);
		sendToAll(packet);
	}

	private void sendTriggerDescTo(ClientInfo clientInfo, TriggerEntry triggers[]) {
		TriggerDescContent content = new TriggerDescContent(1, triggers);
		Packet packet = new Packet(14);
		packet.setContent(content);
		packet.setReciever(clientInfo);
		packetSender.send(packet);
	}

	private void sendTriggerEvent(TriggerEventContent content) {
		Packet packet = new Packet(15);
		packet.setContent(content);
		sendToAll(packet);
		System.out.println(content);
	}

	private void sendDpsParse(DpsParseContent content) {
		Packet packet = new Packet(16);
		packet.setContent(content);
		sendToAll(packet);
	}

	private void setDpsParseSharer(String userName) {
		ClientInfo newDpsSharerInfo = clientManager.getClientInfoByUserName(userName);
		if (newDpsSharerInfo != null) {
			ClientInfo aclientinfo[];
			int j = (aclientinfo = clientManager.getAllClientInfos()).length;
			for (int i = 0; i < j; i++) {
				ClientInfo clientInfo = aclientinfo[i];
				if (clientInfo.isDpsParseSharer()) {
					clientInfo.setDpsParseSharer(false);
					Packet packet = new Packet(11);
					packet.setContent(new ServerCmdContent(11));
					packet.setReciever(clientInfo);
					packetSender.send(packet);
				}
			}

			newDpsSharerInfo.setDpsParseSharer(true);
			Packet packet = new Packet(11);
			packet.setContent(new ServerCmdContent(10));
			packet.setReciever(newDpsSharerInfo);
			packetSender.send(packet);
			sendServerMessage(
					(new StringBuilder(String.valueOf(userName))).append(" ist nun DPS-Parse-Sharer.").toString());
		}
	}

	private void removeDpsParseSharer(String userName) {
		ClientInfo clientInfo = clientManager.getClientInfoByUserName(userName);
		if (clientInfo != null) {
			Packet packet = new Packet(11);
			packet.setContent(new ServerCmdContent(11));
			packet.setReciever(clientInfo);
			packetSender.send(packet);
			sendServerMessage((new StringBuilder(String.valueOf(userName)))
					.append(" ist nun kein DPS-Parse-Sharer mehr.").toString());
		}
	}

	public ClientManager getClientManager() {
		return clientManager;
	}

	public static final int VERSION = 10015;
	private static final int CLIENT_TIMEOUT_DELAY = 30000;
	private static final int CLIENT_LINK_DEAD_DELAY = 10000;
	private static final int CLIENT_INFO_DELAY = 3000;
	private static final String KEY_PORT = "Port";
	private static final String KEY_CHAT_CHANNEL = "ChatChannel";
	boolean running;
	public static final String PTRIGGER = "ptrigger.bin";
	public static final String APHAPS = "Apha-PS.jar";
	public static final String SOUNDSZIP = "sounds.zip";
	private RightsManager rightsManager;
	private TriggerManager triggerManager;
	private ClientManager clientManager;
	PsServerSocket psServerSocket;
	PacketSender packetSender;
	LinkedList recievdPackets;
	LinkedList sentChatPackets;
	long lastClientInfoSent;
	boolean clientListChanged;
	private DelayedLookup clientInfoLookup;
	int port;
	String chatChannel;

}

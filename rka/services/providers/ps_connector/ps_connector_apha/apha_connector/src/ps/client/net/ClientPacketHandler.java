// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ClientPacketHandler.java

package ps.client.net;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.util.LinkedList;
import java.util.Timer;
import java.util.TimerTask;

import ps.net.AddUserContent;
import ps.net.ChangePasswordContent;
import ps.net.ChangeUserRightContent;
import ps.net.ChatContent;
import ps.net.DpsParseContent;
import ps.net.LoginContent;
import ps.net.Packet;
import ps.net.RemoveUserContent;
import ps.net.ServerCmdContent;
import ps.net.TriggerDescContent;
import ps.net.TriggerEventContent;
import ps.util.MD5;

// Referenced classes of package ps.client.net:
//            ServerInfo

public class ClientPacketHandler extends Thread {

	public ClientPacketHandler() {
		connectState = 1;
		running = true;
		authId = MD5.generateAuthId("Gast", "");
		lastRecievedMsgTime = 0L;
		recievdPackets = new LinkedList();
		serverInfo = new ServerInfo(this) {

			@Override
			protected void fireConnectionLost() {
				connectionLost();
			}
		};
		sentPacketList = new LinkedList();
		timer = new Timer(true);
		acknowledgePacket = new Packet(2);
		start();
	}

	public boolean isConnected() {
		return connectState == 4;
	}

	public boolean isDisconnected() {
		return connectState == 1;
	}

	public boolean isTryToLogin() {
		return connectState == 2;
	}

	public boolean isTryToConnect() {
		return connectState == 3;
	}

	private void setAuthId(byte authId[]) {
		this.authId = authId;
	}

	public void sendChatMsg(String sender, String reciever, String msg) {
		if (isConnected()) {
			Packet packet = new Packet(13);
			packet.setContent(new ChatContent(sender, reciever, msg));
			serverInfo.send(packet);
		}
	}

	public void sendAddUser(String userName, String password) {
		if (isConnected()) {
			Packet packet = new Packet(7);
			packet.setContent(new AddUserContent(userName, MD5.generateAuthId(userName, password)));
			serverInfo.send(packet);
		}
	}

	public void sendRemoveUser(String userName) {
		if (isConnected()) {
			Packet packet = new Packet(8);
			packet.setContent(new RemoveUserContent(userName));
			serverInfo.send(packet);
		}
	}

	public void sendChangePassword(String userName, String password) {
		if (isConnected()) {
			Packet packet = new Packet(9);
			packet.setContent(new ChangePasswordContent(userName, MD5.generateAuthId(userName, password)));
			serverInfo.send(packet);
		}
	}

	public void sendChangeUserRight(String userName, int right) {
		if (isConnected()) {
			Packet packet = new Packet(10);
			packet.setContent(new ChangeUserRightContent(userName, right));
			serverInfo.send(packet);
		}
	}

	public void sendTriggerEvent(int triggerId, String triggerAttrStr) {
		if (isConnected()) {
			Packet packet = new Packet(15);
			TriggerEventContent triggerEventContent = new TriggerEventContent(triggerId);
			triggerEventContent.setAttrStr(triggerAttrStr);
			packet.setContent(triggerEventContent);
			serverInfo.send(packet);
		}
	}

	public void sendServerCmd(int cmd) {
		sendServerCmd(cmd, "");
	}

	public void sendServerCmd(int cmd, String param1) {
		if (isConnected()) {
			Packet packet = new Packet(11);
			packet.setContent(new ServerCmdContent(cmd, param1));
			serverInfo.send(packet);
		}
	}

	public void sendServerCmd(int cmd, String param1, String param2) {
		if (isConnected()) {
			Packet packet = new Packet(11);
			packet.setContent(new ServerCmdContent(cmd, param1, param2));
			serverInfo.send(packet);
		}
	}

	public void sendDpsParse(DpsParseContent content) {
		if (isConnected()) {
			Packet packet = new Packet(16);
			packet.setContent(content);
			serverInfo.send(packet);
		}
	}

	public void getUpdate(int n) throws IOException, InterruptedException {
		if (isConnected())
			if (n == 0) {
				Packet packet = new Packet(20);
				packet.setContent(null);
				serverInfo.send(packet);
			} else if (n == 1) {
				Packet packet = new Packet(17);
				packet.setContent(null);
				serverInfo.send(packet);
			} else if (n == 2) {
				Packet packet = new Packet(18);
				packet.setContent(null);
				serverInfo.send(packet);
			} else if (n == 3) {
				Packet packet = new Packet(19);
				packet.setContent(null);
				serverInfo.send(packet);
			}
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
				if (packet != null && (isConnected() || isTryToLogin() || isTryToConnect())) {
					lastRecievedMsgTime = System.currentTimeMillis();
					if (isTryToLogin() || isTryToConnect())
						connected();
					switch (packet.getType()) {
					default:
						break;

					case 12: // '\f'
						serverInfo.send(acknowledgePacket);
						break;

					case 4: // '\004'
						disconnected();
						break;

					case 11: // '\013'
						ServerCmdContent serverCmdCont = (ServerCmdContent) packet.getContent();
						switch (serverCmdCont.getCommand()) {
						}
						break;
					}
					firePacketRecieved(packet);
				} else {
					sleep(50L);
				}
			} catch (Exception ex) {
				ex.printStackTrace();
			}
	}

	private void connected() {
		System.out.println("connected");
		stopLoginTask();
		stopReconnect();
		stopLookupTask();
		connectState = 4;
		lookupTask = new TimerTask() {

			@Override
			public void run() {
				if (System.currentTimeMillis() - lastRecievedMsgTime > 30000L) {
					connectionLost();
					cancel();
				}
			}
		};
		timer.schedule(lookupTask, 0L, 5000L);
		fireConnectionEstablished();
	}

	private void disconnected() {
		System.out.println("disconnected");
		stopLoginTask();
		stopReconnect();
		stopLookupTask();
		connectState = 1;
		serverInfo.disconnect();
		fireDisconnected();
	}

	private void connectionLost() {
		System.out.println("connection lost");
		if (isTryToLogin()) {
			stopLoginTask();
			connectState = 1;
			fireLoginFailed();
		} else {
			connectState = 3;
			fireConnectionLost();
			stopLookupTask();
			stopReconnect();
			reconnectTask = new TimerTask() {

				@Override
				public void run() {
					reconnect();
				}

			};
			timer.schedule(reconnectTask, 1000L, 10000L);
		}
	}

	private void reconnect() {
		System.out.println("reconnect");
		if (!isConnected()) {
			fireTryingToReconnect();
			try {
				serverInfo.reconnect(5000);
				Packet packet = new Packet(3);
				packet.setContent(new LoginContent(authId, 10015));
				serverInfo.send(packet);
			} catch (IOException ioexception) {
			}
		}
	}

	public void startLogin(String host, int port, String password, String user) {
		try {
			serverInfo.connect(new InetSocketAddress(host, port), 5000);
			setAuthId(MD5.generateAuthId(user, password));
			Packet packet = new Packet(3);
			packet.setContent(new LoginContent(authId, 10015));
			connectState = 2;
			serverInfo.send(packet);
			loginTask = new TimerTask() {

				@Override
				public void run() {
					connectState = 1;
					fireLoginFailed();
					cancel();
				}
			};
			timer.schedule(loginTask, 3000L);
		} catch (Exception ex) {
			connectState = 1;
			fireLoginFailed();
		}
	}

	public void login(String host, int port, String user, String password) throws IOException {
		stopReconnect();
		stopLookupTask();
		stopLoginTask();
		if (isDisconnected())
			try {
				serverInfo.connect(new InetSocketAddress(host, port), 5000);
				setAuthId(MD5.generateAuthId(user, password));
				Packet packet = new Packet(3);
				packet.setContent(new LoginContent(authId, 10015));
				connectState = 2;
				serverInfo.send(packet);
				loginTask = new TimerTask() {

					@Override
					public void run() {
						connectState = 1;
						fireLoginFailed();
						cancel();
					}

				};
				timer.schedule(loginTask, 3000L);
			} catch (Exception ex) {
				connectState = 1;
				fireLoginFailed();
			}
	}

	public void logout() {
		System.out.println("logout");
		stopReconnect();
		stopLookupTask();
		stopLoginTask();
		if (serverInfo != null) {
			if (isConnected())
				serverInfo.send(new Packet(4));
			serverInfo.disconnect();
		}
		connectState = 1;
		fireDisconnected();
	}

	private void stopLookupTask() {
		try {
			lookupTask.cancel();
		} catch (Exception exception) {
		}
	}

	private void stopLoginTask() {
		try {
			loginTask.cancel();
		} catch (Exception exception) {
		}
	}

	private void stopReconnect() {
		try {
			reconnectTask.cancel();
		} catch (Exception exception) {
		}
	}

	public void close() {
		try {
			timer.cancel();
		} catch (Exception exception) {
		}
		serverInfo.close();
		this.running = false;
	}

	protected void fireConnectionEstablished() {
	}

	protected void fireConnectionLost() {
	}

	protected void fireDisconnected() {
	}

	protected void fireTryingToReconnect() {
	}

	protected void fireLoginFailed() {
	}

	protected void firePacketRecieved(Packet packet1) {
	}

	public void setCharName(String s) {
	}

	private static final int DISCONNECTED = 1;
	private static final int TRY_TO_LOGIN = 2;
	private static final int TRY_TO_CONNECT = 3;
	private static final int CONNECTED = 4;
	public static final String GETPTRIGGER = "ptrigger.bin";
	public static final String GETSOUNDSZIP = "sounds.zip";
	public static final String GETLIBZIP = "Apha-PS_lib.zip";
	public static final String GETAPHAPS = "Apha-PS.jar";
	int connectState;
	boolean running;
	byte authId[];
	long lastRecievedMsgTime;
	LinkedList recievdPackets;
	ServerInfo serverInfo;
	public ServerInfo PubServerInfo;
	LinkedList sentPacketList;
	Timer timer;
	TimerTask lookupTask;
	TimerTask reconnectTask;
	TimerTask loginTask;
	Packet acknowledgePacket;

}

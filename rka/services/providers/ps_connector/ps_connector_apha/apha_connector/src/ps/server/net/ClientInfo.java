// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ClientInfo.java

package ps.server.net;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.net.SocketException;
import java.net.SocketTimeoutException;

import ps.net.Packet;
import ps.server.ServerPacketHandler;
import ps.server.rights.User;

public class ClientInfo extends Thread {

	public ClientInfo() {
		running = true;
		logedIn = false;
		lastRecievedMsgTime = 0L;
		lastClientInfoSent = 0L;
		ping = 0;
		afk = false;
		logReadActive = false;
		linkDead = false;
		dpsParseSharer = false;
		groupNumber = 0;
		charName = "<unbekannt>";
	}

	public ClientInfo(Socket socket, ServerPacketHandler serverPacketHandler) {
		super((new StringBuilder("ClientInfo ")).append(socket.getInetAddress()).toString());
		running = true;
		logedIn = false;
		lastRecievedMsgTime = 0L;
		lastClientInfoSent = 0L;
		ping = 0;
		afk = false;
		logReadActive = false;
		linkDead = false;
		dpsParseSharer = false;
		groupNumber = 0;
		charName = "<unbekannt>";
		this.socket = socket;
		PubSocket = socket;
		this.serverPacketHandler = serverPacketHandler;
	}

	public void open() throws IOException {
		in = socket.getInputStream();
		out = socket.getOutputStream();
		start();
	}

	public void close() {
		running = false;
		try {
			if (in != null)
				in.close();
			if (out != null)
				out.close();
			if (socket != null) {
				socket.close();
				System.out.println((new StringBuilder("SOCKET CLOSED FROM: "))
						.append(user == null ? "<unknown>" : user.getName()).toString());
			}
		} catch (Exception ex) {
			ex.printStackTrace();
		}
		in = null;
		out = null;
		socket = null;
	}

	synchronized void send(ByteArrayOutputStream buffer) {
		if (running)
			try {
				buffer.writeTo(out);
				out.flush();
			} catch (SocketException ex) {
				if (running)
					serverPacketHandler.fireClientConectionLost(this);
			} catch (IOException ex) {
				if (running) {
					ex.printStackTrace();
					serverPacketHandler.fireClientConectionLost(this);
				}
			}
	}

	@Override
	public void run() {
		while (running)
			try {
				Packet packet = new Packet(this);
				packet.readPacket(in);
				if (packet.getType() >= 0) {
					packet.setTime(System.currentTimeMillis());
					setLastRecievedMsgTime(System.currentTimeMillis());
					serverPacketHandler.addRecievedPacket(packet);
					if (packet.isTypeOf(4))
						running = false;
				} else {
					serverPacketHandler.fireClientConectionLost(this);
				}
			} catch (SocketException ex) {
				if (running)
					serverPacketHandler.fireClientConectionLost(this);
			} catch (SocketTimeoutException ex) {
				if (running)
					serverPacketHandler.fireClientConectionLost(this);
			} catch (Exception ex) {
				if (running) {
					ex.printStackTrace();
					serverPacketHandler.fireClientConectionLost(this);
				}
			}
	}

	public long getLastRecievedMsgTime() {
		return lastRecievedMsgTime;
	}

	public void setLastRecievedMsgTime(long lastRecievedMsgTime) {
		this.lastRecievedMsgTime = lastRecievedMsgTime;
	}

	public void setUser(User user) {
		this.user = user;
	}

	public User getUser() {
		return user;
	}

	public int getPing() {
		return ping;
	}

	public void setPing(int ping) {
		this.ping = ping;
	}

	public boolean isAfk() {
		return afk;
	}

	public void setAfk(boolean afk) {
		this.afk = afk;
	}

	public boolean isLogReadActive() {
		return logReadActive;
	}

	public void setLogReadActive(boolean logReadActive) {
		this.logReadActive = logReadActive;
	}

	public boolean isLinkDead() {
		return linkDead;
	}

	public void setLinkDead(boolean linkDead) {
		this.linkDead = linkDead;
	}

	public boolean isLogedIn() {
		return logedIn;
	}

	public void setLogedIn(boolean logedIn) {
		this.logedIn = logedIn;
	}

	public long getLastClientInfoSent() {
		return lastClientInfoSent;
	}

	public void setLastClientInfoSent(long lastClientInfoSent) {
		this.lastClientInfoSent = lastClientInfoSent;
	}

	public boolean isDpsParseSharer() {
		return dpsParseSharer;
	}

	public void setDpsParseSharer(boolean dpsParseSharer) {
		this.dpsParseSharer = dpsParseSharer;
	}

	public int getGroupNumber() {
		return groupNumber;
	}

	public void setGroupNumber(int groupNumber) {
		this.groupNumber = groupNumber;
	}

	public void setCharName(String charName) {
		this.charName = charName;
	}

	public String getCharName(String charName) {
		return this.charName;
	}

	Socket socket;
	public Socket PubSocket;
	ServerPacketHandler serverPacketHandler;
	InputStream in;
	OutputStream out;
	boolean running;
	boolean logedIn;
	long lastRecievedMsgTime;
	long lastClientInfoSent;
	int ping;
	boolean afk;
	boolean logReadActive;
	boolean linkDead;
	boolean dpsParseSharer;
	int groupNumber;
	String charName;
	User user;
}

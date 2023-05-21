// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ServerInfo.java

package ps.client.net;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.net.SocketAddress;
import java.net.SocketException;

import ps.Main;
import ps.net.Packet;

// Referenced classes of package ps.client.net:
//            ClientPacketHandler

public class ServerInfo extends Thread {

	public ServerInfo(ClientPacketHandler clientPacketHandler) {
		super("ServerInfo");
		buffer = new ByteArrayOutputStream(18432);
		UpdateBuffer = new ByteArrayOutputStream(0x177000);
		running = true;
		connected = false;
		lastRecievedMsgTime = 0L;
		this.clientPacketHandler = clientPacketHandler;
		start();
	}

	public void connect(SocketAddress socketAddress, int timeout) throws IOException {
		this.socketAddress = socketAddress;
		disconnect();
		socket = new Socket();
		socket.setTcpNoDelay(true);
		socket.setPerformancePreferences(0, 1, 0);
		socket.connect(socketAddress, timeout);
		in = socket.getInputStream();
		out = socket.getOutputStream();
		PubServerSocket = socket;
		connected = true;
	}

	public void reconnect(int timeout) throws IOException {
		connect(socketAddress, timeout);
	}

	public void disconnect() {
		connected = false;
		try {
			if (in != null)
				in.close();
			if (out != null)
				out.close();
			if (socket != null) {
				System.out.println("SERVER SOCKET CLOSED");
				socket.close();
			}
		} catch (IOException ex) {
			ex.printStackTrace();
		}
		socket = null;
	}

	public void close() {
		running = false;
		disconnect();
	}

	public synchronized void send(Packet packet) {
	    if (!packet.isTypeOf(Packet.TYPE_ACKNOWLEGE)) {
	        System.out.println(Main.PREFIX_SENDING + packet.toString());
	    }
		if (connected)
			try {
				if (packet.getType() == 21 || packet.getType() == 22) {
					UpdateBuffer.reset();
					packet.writePacket(UpdateBuffer);
					UpdateBuffer.writeTo(out);
					out.flush();
				} else {
					buffer.reset();
					packet.writePacket(buffer);
					buffer.writeTo(out);
					out.flush();
				}
			} catch (SocketException ex) {
				if (running && connected) {
					disconnect();
					fireConnectionLost();
				}
			} catch (IOException ex) {
				if (running && connected) {
					ex.printStackTrace();
					disconnect();
					fireConnectionLost();
				}
			}
	}

	@Override
	public void run() {
		while (running)
			try {
				if (connected) {
					Packet packet = new Packet();
					packet.readPacket(in);
					if (packet.getType() >= 0) {
						setLastRecievedMsgTime(System.currentTimeMillis());
						clientPacketHandler.addRecievedPacket(packet);
						if (packet.isTypeOf(4))
							connected = false;
						Thread.yield();
					} else {
						disconnect();
						fireConnectionLost();
					}
				} else {
					sleep(100L);
				}
			} catch (SocketException ex) {
				if (running && connected) {
					disconnect();
					fireConnectionLost();
				}
			} catch (Exception ex) {
				if (running && connected) {
					ex.printStackTrace();
					disconnect();
					fireConnectionLost();
				}
			}
	}

	public long getLastRecievedMsgTime() {
		return lastRecievedMsgTime;
	}

	public void setLastRecievedMsgTime(long lastRecievedMsgTime) {
		this.lastRecievedMsgTime = lastRecievedMsgTime;
	}

	protected void fireConnectionLost() {
	}

	Socket socket;
	public Socket PubServerSocket;
	SocketAddress socketAddress;
	ByteArrayOutputStream buffer;
	ByteArrayOutputStream UpdateBuffer;
	ClientPacketHandler clientPacketHandler;
	InputStream in;
	OutputStream out;
	boolean running;
	boolean connected;
	long lastRecievedMsgTime;
}

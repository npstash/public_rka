// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   PacketSender.java

package ps.server.net;

import java.io.ByteArrayOutputStream;
import java.util.LinkedList;

import ps.net.Packet;

// Referenced classes of package ps.server.net:
//            ClientInfo

public class PacketSender extends Thread {

	public PacketSender() {
		running = true;
		packetList = new LinkedList();
		buffer = new ByteArrayOutputStream(18432);
		queueEmpty = true;
		start();
	}

	public void stopPacketSender() {
		running = false;
	}

	public void waitForEmptyQueue() {
		while (!queueEmpty)
			try {
			    Thread.yield();
			} catch (Exception ex) {
				ex.printStackTrace();
			}
	}

	@Override
	public void run() {
		while (running)
			try {
				Packet packet = null;
				synchronized (packetList) {
					packet = (Packet) packetList.poll();
				}
				if (packet != null) {
					buffer.reset();
					packet.writePacket(buffer);
					ClientInfo aclientinfo[];
					int j = (aclientinfo = packet.getReciever()).length;
					for (int i = 0; i < j; i++) {
						ClientInfo clientInfo = aclientinfo[i];
						clientInfo.send(buffer);
						Thread.yield();
						if (packet.isTypeOf(12))
							clientInfo.setLastClientInfoSent(System.currentTimeMillis());
					}

				}
				queueEmpty = true;
				sleep(1L);
			} catch (Exception ex) {
				ex.printStackTrace();
			}
	}

	public void send(Packet packet) {
		queueEmpty = false;
		synchronized (packetList) {
			packetList.add(packet);
		}
	}

	private boolean running;
	private LinkedList packetList;
	private ByteArrayOutputStream buffer;
	boolean queueEmpty;
}

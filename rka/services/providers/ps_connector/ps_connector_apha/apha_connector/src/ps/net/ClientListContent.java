// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ClientListContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class ClientListContent implements PacketContent {

	ClientListContent() {
		this(new String[0]);
	}

	public ClientListContent(String clients[]) {
		this.clients = new String[0];
		this.clients = clients;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		out.write(clients.length);
		String as[];
		int j = (as = clients).length;
		for (int i = 0; i < j; i++) {
			String clientName = as[i];
			Packet.writeString(out, clientName);
		}

	}

	@Override
	public void readContent(InputStream in) throws IOException {
		int count = in.read();
		clients = new String[count];
		for (int i = 0; i < clients.length; i++)
			clients[i] = Packet.readString(in);

	}

	@Override
	public String toString() {
		String ret = "[ ClientList |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" clients=\"").toString();
		for (int i = 0; i < clients.length; i++)
			ret = (new StringBuilder(String.valueOf(ret))).append("\"").append(clients[i]).append("\";").toString();

		ret = (new StringBuilder(String.valueOf(ret))).append("\" ]").toString();
		return ret;
	}

	public String[] getClients() {
		return clients;
	}

	public static final String DELIMITER = ";";
	String clients[];
}

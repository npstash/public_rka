// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ClientInfoContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import ps.server.net.ClientInfo;
import ps.server.rights.User;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class ClientInfoContent implements PacketContent {

	ClientInfoContent() {
	}

	public ClientInfoContent(ClientInfo clientInfos[]) {
		this.clientInfos = clientInfos;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		out.write(clientInfos.length);
		for (int i = 0; i < clientInfos.length; i++) {
			Packet.write2ByteNumber(out, clientInfos[i].getPing());
			out.write((clientInfos[i].isAfk() ? 1 : 0) + (clientInfos[i].getUser().getRight() != 1 ? 0 : 2)
					+ (clientInfos[i].isLogReadActive() ? 4 : 0) + (clientInfos[i].isLinkDead() ? 8 : 0));
			out.write(clientInfos[i].getGroupNumber());
		}

	}

	@Override
	public void readContent(InputStream in) throws IOException {
		int count = in.read();
		clientInfos = new ClientInfo[count];
		for (int i = 0; i < count; i++) {
			clientInfos[i] = new ClientInfo();
			clientInfos[i].setPing(Packet.read2ByteNumber(in));
			int status = in.read();
			clientInfos[i].setAfk((status & 1) > 0);
			User user = new User();
			user.setAdmin((status & 2) > 0);
			clientInfos[i].setUser(user);
			clientInfos[i].setLogReadActive((status & 4) > 0);
			clientInfos[i].setLinkDead((status & 8) > 0);
			clientInfos[i].setGroupNumber(in.read());
		}

	}

	@Override
	public String toString() {
		String ret = "[ ClientInfo | ";
		for (int i = 0; i < clientInfos.length; i++) {
			ret = (new StringBuilder(String.valueOf(ret))).append("[").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" ping=\"").append(clientInfos[i].getPing())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" afk=\"").append(clientInfos[i].isAfk()).append("\"")
					.toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" admin=\"")
					.append(clientInfos[i].getUser().isAdmin()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" logReadAvtive=\"")
					.append(clientInfos[i].isLogReadActive()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" groupNumber=\"")
					.append(clientInfos[i].getGroupNumber()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		}

		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public ClientInfo[] getClientInfos() {
		return clientInfos;
	}

	ClientInfo clientInfos[];
}

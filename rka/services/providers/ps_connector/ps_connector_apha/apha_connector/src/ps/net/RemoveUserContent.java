// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   RemoveUserContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class RemoveUserContent implements PacketContent {

	RemoveUserContent() {
		userName = "";
	}

	public RemoveUserContent(String userName) {
		this.userName = "";
		this.userName = userName;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		Packet.writeString(out, userName);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		userName = Packet.readString(in);
	}

	@Override
	public String toString() {
		String ret = "[ RemoveUser |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" userName=").append(userName).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public String getUserName() {
		return userName;
	}

	String userName;
}

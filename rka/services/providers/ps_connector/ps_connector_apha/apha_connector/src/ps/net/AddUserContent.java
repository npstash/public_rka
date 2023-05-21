// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   AddUserContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class AddUserContent implements PacketContent {

	AddUserContent() {
		userName = "";
		authId = new byte[16];
	}

	public AddUserContent(String userName, byte authId[]) {
		this.userName = "";
		this.authId = new byte[16];
		this.userName = userName;
		this.authId = authId;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		Packet.writeString(out, userName);
		out.write(authId);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		userName = Packet.readString(in);
		in.read(authId);
	}

	@Override
	public String toString() {
		String ret = "[ AddUser |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" userName=").append(userName).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" authId=################").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public String getUserName() {
		return userName;
	}

	public byte[] getAuthId() {
		return authId;
	}

	String userName;
	byte authId[];
}

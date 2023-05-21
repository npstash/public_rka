// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ChangeUserRightContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class ChangeUserRightContent implements PacketContent {

	ChangeUserRightContent() {
		right = 0;
		userName = "";
	}

	public ChangeUserRightContent(String userName, int right) {
		this.right = 0;
		this.userName = "";
		this.userName = userName;
		this.right = right;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		out.write(right);
		Packet.writeString(out, userName);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		right = in.read();
		userName = Packet.readString(in);
	}

	@Override
	public String toString() {
		String ret = "[ ChangeUserRight |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" userName=").append(userName).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" right=").append(right).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public String getUserName() {
		return userName;
	}

	public int getRight() {
		return right;
	}

	int right;
	String userName;
}

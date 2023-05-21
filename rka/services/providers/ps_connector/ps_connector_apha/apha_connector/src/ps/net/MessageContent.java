// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   MessageContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class MessageContent implements PacketContent {

	MessageContent() {
		this("");
	}

	public MessageContent(String msg) {
		this.msg = "";
		this.msg = msg;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		Packet.writeString(out, msg);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		msg = Packet.readString(in);
	}

	@Override
	public String toString() {
		String ret = "[ Message |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" msg=\"").append(msg).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public String getMsg() {
		return msg;
	}

	public void setMsg(String msg) {
		this.msg = msg;
	}

	String msg;
}

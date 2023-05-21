// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ChatContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class ChatContent implements PacketContent {

	ChatContent() {
		this("<unbekannt>", "", "");
	}

	public ChatContent(String sender, String reciever, String msg) {
		this.sender = sender;
		this.reciever = reciever;
		this.msg = msg;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		Packet.writeString(out, sender);
		Packet.writeString(out, reciever);
		Packet.writeString(out, msg);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		sender = Packet.readString(in);
		reciever = Packet.readString(in);
		msg = Packet.readString(in);
	}

	@Override
	public String toString() {
		String ret = "[ Message |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" sender=\"").append(sender).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" reciever=\"").append(reciever).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" msg=\"").append(msg).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public void setSender(String sender) {
		this.sender = sender;
	}

	public String getSender() {
		return sender;
	}

	public String getReciever() {
		return reciever;
	}

	public String getMsg() {
		return msg;
	}

	public static final String TO_ALL_PS_CLIENTS = "";
	String sender;
	String reciever;
	String msg;
}

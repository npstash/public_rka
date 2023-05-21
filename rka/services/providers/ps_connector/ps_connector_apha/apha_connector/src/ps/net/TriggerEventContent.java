// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   TriggerEventContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class TriggerEventContent implements PacketContent {

	TriggerEventContent() {
		sender = "";
		attrStr = "";
	}

	public TriggerEventContent(int triggerId) {
		sender = "";
		attrStr = "";
		this.triggerId = triggerId;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		Packet.write2ByteNumber(out, triggerId);
		Packet.writeString(out, sender);
		Packet.writeString(out, attrStr);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		triggerId = Packet.read2ByteNumber(in);
		sender = Packet.readString(in);
		attrStr = Packet.readString(in);
	}

	@Override
	public String toString() {
		String ret = "[ TriggerEvent |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" triggerId=\"").append(triggerId).append("\"")
				.toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" sender=\"").append(sender).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" attrStr=\"").append(attrStr).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public int getTriggerId() {
		return triggerId;
	}

	public String getSender() {
		return sender;
	}

	public void setSender(String sender) {
		this.sender = sender;
	}

	public String getAttrStr() {
		return attrStr;
	}

	public void setAttrStr(String attrStr) {
		this.attrStr = attrStr;
	}

	int triggerId;
	String sender;
	String attrStr;
}

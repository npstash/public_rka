// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   Packet.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import ps.server.net.ClientInfo;

// Referenced classes of package ps.net:
//            PacketContent, LoginContent, MessageContent, ClientListContent, 
//            AddUserContent, RemoveUserContent, ChangePasswordContent, ChangeUserRightContent, 
//            ServerCmdContent, ClientInfoContent, ChatContent, TriggerDescContent, 
//            TriggerEventContent, DpsParseContent

public class Packet {

	public Packet() {
		type = 0;
		SizeStep = 0;
		content = null;
		time = 0L;
		reciever = new ClientInfo[0];
		resendCount = 0;
	}

	public Packet(ClientInfo sender) {
		type = 0;
		SizeStep = 0;
		content = null;
		time = 0L;
		reciever = new ClientInfo[0];
		resendCount = 0;
		this.sender = sender;
	}

	public Packet(int type) {
		this.type = 0;
		SizeStep = 0;
		content = null;
		time = 0L;
		reciever = new ClientInfo[0];
		resendCount = 0;
		this.type = type;
	}

	public Packet(int type, int SizeStep) {
		this.type = 0;
		this.SizeStep = 0;
		content = null;
		time = 0L;
		reciever = new ClientInfo[0];
		resendCount = 0;
		this.type = type;
		this.SizeStep = SizeStep;
	}

	public void writePacket(OutputStream out) throws IOException {
		out.write(type);
		if (content != null)
			content.writeContent(out);
	}

	public void readPacket(InputStream in) throws IOException {
		type = in.read();
		content = getInstanceByType(type);
		if (content != null)
			content.readContent(in);
	}

	@Override
	public String toString() {
		String ret = (new StringBuilder("[ type=")).append(type).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(content != null ? content.toString() : "[]").toString();
		return ret;
	}

	private static PacketContent getInstanceByType(int type) {
		PacketContent ret = null;
		ret = (type != 3 ? ret : ((PacketContent) (new LoginContent())));
		ret = (type != 5 ? ret : ((PacketContent) (new MessageContent())));
		ret = (type != 6 ? ret : ((PacketContent) (new ClientListContent())));
		ret = (type != 7 ? ret : ((PacketContent) (new AddUserContent())));
		ret = (type != 8 ? ret : ((PacketContent) (new RemoveUserContent())));
		ret = (type != 9 ? ret : ((PacketContent) (new ChangePasswordContent())));
		ret = (type != 10 ? ret : ((PacketContent) (new ChangeUserRightContent())));
		ret = (type != 11 ? ret : ((PacketContent) (new ServerCmdContent())));
		ret = (type != 12 ? ret : ((PacketContent) (new ClientInfoContent())));
		ret = (type != 13 ? ret : ((PacketContent) (new ChatContent())));
		ret = (type != 14 ? ret : ((PacketContent) (new TriggerDescContent())));
		ret = (type != 15 ? ret : ((PacketContent) (new TriggerEventContent())));
		ret = (type != 16 ? ret : ((PacketContent) (new DpsParseContent())));
		return ret;
	}

	public static void writeString(OutputStream out, String str) throws IOException {
		byte strBytes[] = str.getBytes("Cp1250");
		if (strBytes.length > 255)
			strBytes = str.substring(0, 255).getBytes("Cp1250");
		out.write(strBytes.length);
		out.write(strBytes);
	}

	public static void writeNoString(OutputStream out, String str) throws IOException {
		str = "";
		byte strBytes[] = str.getBytes("Cp1250");
		if (strBytes.length > 255)
			strBytes = str.substring(0, 255).getBytes("Cp1250");
		out.write(strBytes.length);
		out.write(strBytes);
	}

	public static String readString(InputStream in) throws IOException {
		int length = in.read();
		byte bytes[] = new byte[length];
		for (int i = 0; i < bytes.length; i++)
			bytes[i] = (byte) in.read();

		return new String(bytes, "Cp1250");
	}

	public static String setString() throws IOException {
		int length = 0;
		byte bytes[] = new byte[length];
		return new String(bytes, "Cp1250");
	}

	public static void write2ByteNumber(OutputStream out, int number) throws IOException {
		short shortNumber = (short) number;
		out.write((byte) (shortNumber >>> 8));
		out.write((byte) shortNumber);
	}

	public static int read2ByteNumber(InputStream in) throws IOException {
		int b1 = in.read();
		int b2 = in.read();
		int number = (b1 << 8) + b2;
		return number;
	}

	public static void writeBoolean(OutputStream out, boolean b) throws IOException {
		out.write(b ? 1 : 0);
	}

	public static void writeBooleanFalse(OutputStream out, boolean b) throws IOException {
		out.write(0);
	}

	public static boolean readBoolean(InputStream in) throws IOException {
		return in.read() > 0;
	}

	public void setType(int type) {
		this.type = type;
	}

	public int getType() {
		return type;
	}

	public boolean isTypeOf(int type) {
		return this.type == type;
	}

	public PacketContent getContent() {
		return content;
	}

	public void setContent(PacketContent packetContent) {
		content = packetContent;
	}

	public long getTime() {
		return time;
	}

	public void setTime(long time) {
		this.time = time;
	}

	public void setResendCount(int resendCount) {
		this.resendCount = resendCount;
	}

	public int getResentCount() {
		return resendCount;
	}

	public ClientInfo getSender() {
		return sender;
	}

	public void setSender(ClientInfo sender) {
		this.sender = sender;
	}

	public ClientInfo[] getReciever() {
		return reciever;
	}

	public void setReciever(ClientInfo reciever[]) {
		this.reciever = reciever;
	}

	public void setReciever(ClientInfo reciever) {
		this.reciever = (new ClientInfo[] { reciever });
	}

	public static final int TYPE_UNDEFINED = 0;
	public static final int TYPE_PING = 1;
	public static final int TYPE_ACKNOWLEGE = 2;
	public static final int TYPE_LOGIN = 3;
	public static final int TYPE_LOGOUT = 4;
	public static final int TYPE_MESSAGE = 5;
	public static final int TYPE_CLIENT_LIST = 6;
	public static final int TYPE_ADD_USER = 7;
	public static final int TYPE_REMOVE_USER = 8;
	public static final int TYPE_CHANGE_PASSWORD = 9;
	public static final int TYPE_CHANGE_USER_RIGHT = 10;
	public static final int TYPE_SERVER_CMD = 11;
	public static final int TYPE_CLIENT_INFO = 12;
	public static final int TYPE_CHAT = 13;
	public static final int TYPE_TRIGGER_DESC = 14;
	public static final int TYPE_TRIGGER_EVENT = 15;
	public static final int TYPE_DPS_PARSE = 16;
	public static final int TYPE_GET_UPDATE1 = 17;
	public static final int TYPE_GET_UPDATE2 = 18;
	public static final int TYPE_GET_UPDATE3 = 19;
	public static final int TYPE_GET_UPDATE0 = 20;
	public static final int TYPE_SET_UPDATE2 = 21;
	public static final int TYPE_SET_UPDATE3 = 22;
	public static final String ENCODING = "Cp1250";
	int type;
	int SizeStep;
	PacketContent content;
	long time;
	ClientInfo sender;
	ClientInfo reciever[];
	int resendCount;
}

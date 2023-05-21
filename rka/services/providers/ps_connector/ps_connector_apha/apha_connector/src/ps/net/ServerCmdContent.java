// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ServerCmdContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class ServerCmdContent implements PacketContent {

	ServerCmdContent() {
		command = 0;
		param1 = "";
		param2 = "";
	}

	public ServerCmdContent(int cmd) {
		command = 0;
		param1 = "";
		param2 = "";
		command = cmd;
	}

	public ServerCmdContent(int cmd, String param1) {
		command = 0;
		this.param1 = "";
		param2 = "";
		command = cmd;
		this.param1 = param1;
	}

	public ServerCmdContent(int cmd, String param1, String param2) {
		command = 0;
		this.param1 = "";
		this.param2 = "";
		command = cmd;
		this.param1 = param1;
		this.param2 = param2;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		out.write(command);
		Packet.writeString(out, param1);
		Packet.writeString(out, param2);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		command = in.read();
		param1 = Packet.readString(in);
		param2 = Packet.readString(in);
	}

	@Override
	public String toString() {
		String ret = "[ ServerCommand |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" cmd=").append(command).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" param1=").append(param1).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" param2=").append(param2).toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public int getCommand() {
		return command;
	}

	public String getParam1() {
		return param1;
	}

	public String getParam2() {
		return param2;
	}

	public void setParam1(String param1) {
		this.param1 = param1;
	}

	public void setParam2(String param2) {
		this.param2 = param2;
	}

	public static final int CMD_NONE = 0;
	public static final int CMD_SHOW_ADMIN_TOOLS = 1;
	public static final int CMD_HIDE_ADMIN_TOOLS = 2;
	public static final int CMD_CLIENT_LOGGED_IN = 3;
	public static final int CMD_CLIENT_LOGGED_OUT = 4;
	public static final int CMD_CLIENT_GOES_AFK = 5;
	public static final int CMD_CLIENT_COMES_BACK = 6;
	public static final int CMD_CLIENT_LOG_READ_ACTIVE = 7;
	public static final int CMD_CLIENT_LOG_READ_INACTIVE = 8;
	public static final int CMD_UPDATE_CLIENT = 9;
	public static final int CMD_SET_DPS_PARSE_SHARER = 10;
	public static final int CMD_REMOVE_DPS_PARSE_SHARER = 11;
	public static final int CMD_SET_CHAT_CHANNEL = 12;
	public static final int CMD_SET_GROUP_NUMBER = 13;
	int command;
	String param1;
	String param2;
}

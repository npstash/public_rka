// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   LoginContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class LoginContent implements PacketContent {

	LoginContent() {
	}

	public LoginContent(byte authId[], int version) {
		this.authId = authId;
		this.version = version;
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		out.write(authId);
		Packet.write2ByteNumber(out, version);
	}

	@Override
	public void readContent(InputStream in) throws IOException {
		authId = new byte[16];
		in.read(authId);
		version = Packet.read2ByteNumber(in);
	}

	@Override
	public String toString() {
		String ret = "[ Auth |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" authId=\"").toString();
		for (int i = 0; i < authId.length; i++)
			ret = (new StringBuilder(String.valueOf(ret))).append(authId[i]).append(";").toString();

		ret = (new StringBuilder(String.valueOf(ret))).append(" version=\"").append(version).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" \" ]").toString();
		return ret;
	}

	public byte[] getAuthId() {
		return authId;
	}

	public void setAuthId(byte authId[]) {
		this.authId = authId;
	}

	public int getVersion() {
		return version;
	}

	public void setVersion(int version) {
		this.version = version;
	}

	byte authId[];
	int version;
}

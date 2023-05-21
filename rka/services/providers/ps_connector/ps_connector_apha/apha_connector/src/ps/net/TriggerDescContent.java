// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   TriggerDescContent.java

package ps.net;

import java.awt.Color;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

import ps.server.trigger.TriggerEntry;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class TriggerDescContent implements PacketContent {

	TriggerDescContent() {
		zipedBytes = new ByteArrayOutputStream(16384);
	}

	public TriggerDescContent(int cmd, TriggerEntry trigger) {
		this(cmd, new TriggerEntry[] { trigger });
	}

	public TriggerDescContent(int cmd, TriggerEntry triggers[]) {
		zipedBytes = new ByteArrayOutputStream(16384);
		this.cmd = cmd;
		this.triggers = triggers;
		try {
			zipContent(zipedBytes);
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		zipedBytes.writeTo(out);
	}

	private void zipContent(OutputStream out) throws IOException {
		ZipOutputStream zipOut = new ZipOutputStream(out);
		zipOut.putNextEntry(new ZipEntry("TriggerDescContent"));
		writeContentUncompressed(zipOut);
		zipOut.closeEntry();
	}

	private void writeContentUncompressed(OutputStream out) throws IOException {
		out.write(cmd);
		Packet.write2ByteNumber(out, triggers.length);
		for (int i = 0; i < triggers.length; i++) {
			Packet.write2ByteNumber(out, triggers[i].getId());
			Packet.writeString(out, triggers[i].getTitle());
			Packet.writeBoolean(out, triggers[i].isActive());
			Packet.writeString(out, triggers[i].getCategory());
			Packet.writeString(out, triggers[i].getRegex());
			Packet.writeString(out, triggers[i].getReact());
			Packet.write2ByteNumber(out, triggers[i].getQuantity());
			Packet.write2ByteNumber(out, triggers[i].getIgnoreTimer());
			Packet.writeBoolean(out, triggers[i].isServerMsgActive());
			Packet.writeString(out, triggers[i].getServerMsg());
			out.write(triggers[i].getServerMsgSize());
			out.write(triggers[i].getServerMsgColor().getRed());
			out.write(triggers[i].getServerMsgColor().getGreen());
			out.write(triggers[i].getServerMsgColor().getBlue());
			Packet.writeBoolean(out, triggers[i].isSoundActive());
			Packet.writeString(out, triggers[i].getSound());
			Packet.writeBoolean(out, triggers[i].isTimerActive());
			Packet.writeBoolean(out, triggers[i].isTimerShow1());
			Packet.writeBoolean(out, triggers[i].isTimerShow2());
			Packet.writeBoolean(out, triggers[i].isTimerShow3());
			Packet.write2ByteNumber(out, triggers[i].getTimerPeriod());
			Packet.write2ByteNumber(out, triggers[i].getTimerWarning());
			Packet.writeString(out, triggers[i].getTimerWarningMsg());
			out.write(triggers[i].getTimerWarningMsgSize());
			out.write(triggers[i].getTimerWarningMsgColor().getRed());
			out.write(triggers[i].getTimerWarningMsgColor().getGreen());
			out.write(triggers[i].getTimerWarningMsgColor().getBlue());
			Packet.writeString(out, triggers[i].getTimerWarningSound());
			Packet.write2ByteNumber(out, triggers[i].getTimerRemove());
			Packet.writeBoolean(out, triggers[i].getPrivatSound());
		}

	}

	@Override
	public void readContent(InputStream in) throws IOException {
		ZipInputStream zipIn = new ZipInputStream(in);
		ZipEntry entry = zipIn.getNextEntry();
		if (entry != null)
			readContentUncompressed(zipIn);
		zipIn.closeEntry();
	}

	public void readContentUncompressed(InputStream in) throws IOException {
		cmd = in.read();
		int length = Packet.read2ByteNumber(in);
		triggers = new TriggerEntry[length];
		for (int i = 0; i < triggers.length; i++) {
			triggers[i] = new TriggerEntry();
			triggers[i].setId(Packet.read2ByteNumber(in));
			triggers[i].setTitle(Packet.readString(in));
			triggers[i].setActive(Packet.readBoolean(in));
			triggers[i].setCategory(Packet.readString(in));
			triggers[i].setRegex(Packet.readString(in));
			triggers[i].setReact(Packet.readString(in));
			triggers[i].setQuantity(Packet.read2ByteNumber(in));
			triggers[i].setIgnoreTimer(Packet.read2ByteNumber(in));
			triggers[i].setServerMsgActive(Packet.readBoolean(in));
			triggers[i].setServerMsg(Packet.readString(in));
			triggers[i].setServerMsgSize(in.read());
			int red = in.read();
			int green = in.read();
			int blue = in.read();
			triggers[i].setServerMsgColor(new Color(red, green, blue));
			triggers[i].setSoundActive(Packet.readBoolean(in));
			triggers[i].setSound(Packet.readString(in));
			triggers[i].setTimerActive(Packet.readBoolean(in));
			triggers[i].setTimerShow1(Packet.readBoolean(in));
			triggers[i].setTimerShow2(Packet.readBoolean(in));
			triggers[i].setTimerShow3(Packet.readBoolean(in));
			triggers[i].setTimerPeriod(Packet.read2ByteNumber(in));
			triggers[i].setTimerWarning(Packet.read2ByteNumber(in));
			triggers[i].setTimerWarningMsg(Packet.readString(in));
			triggers[i].setTimerWarningMsgSize(in.read());
			red = in.read();
			green = in.read();
			blue = in.read();
			triggers[i].setTimerWarningMsgColor(new Color(red, green, blue));
			triggers[i].setTimerWarningSound(Packet.readString(in));
			triggers[i].setTimerRemove(Packet.read2ByteNumber(in));
			triggers[i].setPrivatSound(Packet.readBoolean(in));
		}

	}

	@Override
	public String toString() {
		String ret = "[ TriggerDesc |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" cmd=\"").append(cmd).append("\"").toString();
		for (int i = 0; i < triggers.length; i++) {
			ret = (new StringBuilder(String.valueOf(ret))).append("\r\n    ").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" id=\"").append(triggers[i].getId()).append("\"")
					.toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" title=\"").append(triggers[i].getTitle())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" active=\"").append(triggers[i].isActive())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" category=\"").append(triggers[i].getCategory())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" regex=\"").append(triggers[i].getRegex())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" react=\"").append(triggers[i].getReact())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" quantity=\"").append(triggers[i].getQuantity())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" ignoreTimer=\"")
					.append(triggers[i].getIgnoreTimer()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" serverMsgActive=\"")
					.append(triggers[i].isServerMsgActive()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" serverMsg=\"").append(triggers[i].getServerMsg())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" size=\"").append(triggers[i].getServerMsgSize())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" color=\"").append(triggers[i].getServerMsgColor())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" soundActive=\"").append(triggers[i].isSoundActive())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" sound=\"").append(triggers[i].getSound())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerActive=\"").append(triggers[i].isTimerActive())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerShow1=\"").append(triggers[i].isTimerShow1())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerShow2=\"").append(triggers[i].isTimerShow2())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerShow3=\"").append(triggers[i].isTimerShow3())
					.append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerPeriod=\"")
					.append(triggers[i].getTimerPeriod()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerWarning=\"")
					.append(triggers[i].getTimerWarning()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerWarningMsg=\"")
					.append(triggers[i].getTimerWarningMsg()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerWarningMsgSize=\"")
					.append(triggers[i].getTimerWarningMsgSize()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerWarningMsgColor=\"")
					.append(triggers[i].getTimerWarningMsgColor()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerWarningMsgSound=\"")
					.append(triggers[i].getTimerWarningSound()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" timerRemove=\"")
					.append(triggers[i].getTimerRemove()).append("\"").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" privatSound=\"")
					.append(triggers[i].getPrivatSound()).append("\"").toString();
		}

		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public int getCmd() {
		return cmd;
	}

	public TriggerEntry getTriggerEntry() {
		return triggers[0];
	}

	public TriggerEntry[] getTriggerEntries() {
		return triggers;
	}

	public static final int CMD_ADD = 1;
	public static final int CMD_REMOVE = 2;
	public static final String NO_CATEGORY = "<keine Kategorie>";
	int cmd;
	TriggerEntry triggers[];
	ByteArrayOutputStream zipedBytes;
}

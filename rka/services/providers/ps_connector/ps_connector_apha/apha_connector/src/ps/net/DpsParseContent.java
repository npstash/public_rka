// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   DpsParseContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import ps.client.gui.dpsoverlay.DpsListEntry;

// Referenced classes of package ps.net:
//            PacketContent, Packet

public class DpsParseContent implements PacketContent {

	public DpsParseContent() {
	}

	@Override
	public void writeContent(OutputStream out) throws IOException {
		Packet.writeString(out, title);
		Packet.writeString(out, time);
		Packet.writeString(out, damage);
		Packet.writeString(out, dps);
		out.write(dpsListEntries.length);
		DpsListEntry adpslistentry[];
		int j = (adpslistentry = dpsListEntries).length;
		for (int i = 0; i < j; i++) {
			DpsListEntry entry = adpslistentry[i];
			Packet.writeString(out, entry.getName());
			Packet.writeString(out, entry.getDps());
		}

	}

	@Override
	public void readContent(InputStream in) throws IOException {
		title = Packet.readString(in);
		time = Packet.readString(in);
		damage = Packet.readString(in);
		dps = Packet.readString(in);
		int count = in.read();
		dpsListEntries = new DpsListEntry[count];
		for (int i = 0; i < dpsListEntries.length; i++) {
			dpsListEntries[i] = new DpsListEntry();
			dpsListEntries[i].setName(Packet.readString(in));
			dpsListEntries[i].setDps(Packet.readString(in));
		}

	}

	@Override
	public String toString() {
		String ret = "[ DpsParse |";
		ret = (new StringBuilder(String.valueOf(ret))).append(" title=\"").append(title).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" time=\"").append(time).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" damage=\"").append(damage).append("\"").toString();
		ret = (new StringBuilder(String.valueOf(ret))).append(" dps=\"").append(dps).append("\"").toString();
		DpsListEntry adpslistentry[];
		int j = (adpslistentry = dpsListEntries).length;
		for (int i = 0; i < j; i++) {
			DpsListEntry entry = adpslistentry[i];
			ret = (new StringBuilder(String.valueOf(ret))).append("\r\n").toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" name=\"").append(entry.getName()).append("\"")
					.toString();
			ret = (new StringBuilder(String.valueOf(ret))).append(" dps=\"").append(entry.getDps()).append("\"")
					.toString();
		}

		ret = (new StringBuilder(String.valueOf(ret))).append(" ]").toString();
		return ret;
	}

	public String getTitle() {
		return title;
	}

	public void setTitle(String title) {
		this.title = title;
	}

	public String getTime() {
		return time;
	}

	public void setTime(String time) {
		this.time = time;
	}

	public String getDps() {
		return dps;
	}

	public void setDps(String dps) {
		this.dps = dps;
	}

	public DpsListEntry[] getDpsListEntries() {
		return dpsListEntries;
	}

	public void setDpsListEntries(DpsListEntry dpsListEntries[]) {
		this.dpsListEntries = dpsListEntries;
	}

	public String getDamage() {
		return damage;
	}

	public void setDamage(String damage) {
		this.damage = damage;
	}

	String title;
	String time;
	String damage;
	String dps;
	DpsListEntry dpsListEntries[];
}

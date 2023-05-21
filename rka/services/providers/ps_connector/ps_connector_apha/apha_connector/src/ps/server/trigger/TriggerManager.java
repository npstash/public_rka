// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   TriggerManager.java

package ps.server.trigger;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.Vector;

import ps.net.TriggerDescContent;

// Referenced classes of package ps.server.trigger:
//            TriggerEntry

public class TriggerManager {

	public TriggerManager() {
		this(DEF_SAVE_FILE_NAME);
	}

	public TriggerManager(String saveFileName) {
		triggers = new TriggerEntry[0];
		triggerList = new Vector();
		nextTriggerId = 0;
		this.saveFileName = saveFileName;
		load();
		triggers = createTriggerArray();
	}

	public void addTrigger(TriggerEntry entry) {
		if (triggerList.contains(entry))
			triggerList.remove(entry);
		entry.setId(nextTriggerId);
		nextTriggerId++;
		triggerList.add(entry);
		triggers = createTriggerArray();
		save();
	}

	public void addTriggers(TriggerEntry entries[]) {
		TriggerEntry atriggerentry[];
		int j = (atriggerentry = entries).length;
		for (int i = 0; i < j; i++) {
			TriggerEntry entry = atriggerentry[i];
			if (triggerList.contains(entry))
				triggerList.remove(entry);
			entry.setId(nextTriggerId);
			nextTriggerId++;
			triggerList.add(entry);
		}

		triggers = createTriggerArray();
		save();
	}

	public void removeTrigger(TriggerEntry entry) {
		triggerList.remove(entry);
		triggers = createTriggerArray();
		save();
	}

	public TriggerEntry getTriggerByTitle(String str) {
		TriggerEntry atriggerentry[];
		int j = (atriggerentry = triggers).length;
		for (int i = 0; i < j; i++) {
			TriggerEntry entry = atriggerentry[i];
			if (entry.getTitle().equalsIgnoreCase(str))
				return entry;
		}

		return null;
	}

	public TriggerEntry getTriggerById(int id) {
		TriggerEntry atriggerentry[];
		int j = (atriggerentry = triggers).length;
		for (int i = 0; i < j; i++) {
			TriggerEntry entry = atriggerentry[i];
			if (entry.getId() == id)
				return entry;
		}

		return null;
	}

	private TriggerEntry[] createTriggerArray() {
		return (TriggerEntry[]) triggerList.toArray(new TriggerEntry[triggerList.size()]);
	}

	public TriggerEntry[] getAllTrigger() {
		return triggers;
	}

	public void setTriggerEntries(TriggerEntry entries[]) {
		triggerList.clear();
		for (int i = 0; i < entries.length; i++) {
			entries[i].setId(nextTriggerId);
			nextTriggerId++;
			triggerList.add(entries[i]);
		}

		triggers = createTriggerArray();
	}

	public void save() {
		try {
			FileOutputStream out = new FileOutputStream(saveFileName);
			TriggerDescContent cont = new TriggerDescContent(1, triggers);
			cont.writeContent(out);
			out.flush();
			out.close();
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	private void load() {
		try {
			if ((new File(saveFileName)).exists()) {
				TriggerDescContent cont = new TriggerDescContent(1, new TriggerEntry[0]);
				FileInputStream in = new FileInputStream(saveFileName);
				cont.readContent(in);
				in.close();
				setTriggerEntries(cont.getTriggerEntries());
			}
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	private static String DEF_SAVE_FILE_NAME = "trigger.bin";
	TriggerEntry triggers[];
	Vector triggerList;
	int nextTriggerId;
	private String saveFileName;

}

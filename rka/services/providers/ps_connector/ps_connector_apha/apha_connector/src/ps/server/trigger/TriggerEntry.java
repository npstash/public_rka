// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   TriggerEntry.java

package ps.server.trigger;

import java.awt.Color;
import java.util.HashSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import ps.net.TriggerEventContent;

public class TriggerEntry {

	public TriggerEntry() {
		id = 0;
		title = "";
		active = true;
		category = "";
		regex = "";
		react = "";
		reactDo = "";
		quantity = 1;
		ignoreTimer = 20;
		serverMsgActive = false;
		serverMsg = "";
		serverMsgSize = 12;
		serverMsgColor = Color.WHITE;
		soundActive = false;
		sound = "<kein>";
		timerActive = false;
		timerShow1 = true;
		timerShow2 = false;
		timerShow3 = false;
		privatSound = false;
		timerPeriod = 42;
		timerWarning = 8;
		timerWarningMsg = "";
		timerWarningMsgSize = 12;
		timerWarningMsgColor = Color.WHITE;
		timerWarningSound = "<kein>";
		timerRemove = 15;
		firstTriggerTime = 0L;
		triggerCount = 0;
		message = "";
		message2 = "";
		solvedServerMessage = "";
		solvedTimerWarningMessage = "";
		attrStrings = new HashSet();
	}

	@Override
	public String toString() {
		return title;
	}

	@Override
	public boolean equals(Object o) {
		return o != null && (o instanceof TriggerEntry) && title.equalsIgnoreCase(o.toString());
	}

	@Override
	public Object clone() {
		TriggerEntry ret = new TriggerEntry();
		ret.id = getId();
		ret.title = getTitle();
		ret.active = isActive();
		ret.category = getCategory();
		ret.regex = getRegex();
		ret.react = getReact();
		ret.reactDo = getReactDo();
		ret.quantity = getQuantity();
		ret.ignoreTimer = getIgnoreTimer();
		ret.serverMsgActive = isServerMsgActive();
		ret.serverMsg = getServerMsg();
		ret.serverMsgSize = getServerMsgSize();
		ret.serverMsgColor = getServerMsgColor();
		ret.soundActive = isSoundActive();
		ret.sound = getSound();
		ret.timerActive = isTimerActive();
		ret.timerShow1 = isTimerShow1();
		ret.timerShow2 = isTimerShow2();
		ret.timerShow3 = isTimerShow3();
		ret.timerPeriod = getTimerPeriod();
		ret.timerWarning = getTimerWarning();
		ret.timerWarningMsg = getTimerWarningMsg();
		ret.timerWarningMsgSize = getTimerWarningMsgSize();
		ret.timerWarningMsgColor = getTimerWarningMsgColor();
		ret.timerWarningSound = getTimerWarningSound();
		ret.timerRemove = getTimerRemove();
		ret.privatSound = getPrivatSound();
		return ret;
	}

	public void solveServerMsg(TriggerEventContent triggerEvtCont) {
		solvedServerMessage = solveMessage(getServerMsg(), triggerEvtCont);
		message = solvedServerMessage;
		if (getReact() != "")
			reactDo = solveMessage(getReact(), triggerEvtCont);
	}

	public void solveTimerWarningMessage(TriggerEventContent triggerEvtCont) {
		solvedTimerWarningMessage = solveMessage(getTimerWarningMsg(), triggerEvtCont);
	}

	private String solveMessage(String msg, TriggerEventContent triggerEvtCont) {
		if (msg.length() > 0) {
			String triggerAttr[] = triggerEvtCont.getAttrStr().split(";");
			System.out.println((new StringBuilder("triggerEvtCont.getAttrStr() = ")).append(triggerEvtCont.getAttrStr())
					.append(" mit ").append(triggerAttr.length).toString());
			StringBuilder solvedMsg = new StringBuilder();
			int newContentIndex = 0;
			for (Matcher matcher = CUSTOM_VAR_PATTERN.matcher(msg); matcher.find();) {
				solvedMsg.append(msg.substring(newContentIndex, matcher.start()));
				newContentIndex = matcher.end();
				if (msg.substring(matcher.start()).startsWith("%u"))
					solvedMsg.append(triggerEvtCont.getSender());
				else if (triggerAttr.length <= 10)
					if (msg.substring(matcher.start()).startsWith("%s"))
						System.out.println((new StringBuilder("triggerAttr[0] ")).append(triggerAttr[0]).toString());
					else if (msg.substring(matcher.start()).startsWith("%a"))
						solvedMsg.append(triggerAttr[1]);
					else if (msg.substring(matcher.start()).startsWith("%t"))
						solvedMsg.append(triggerAttr[2]);
					else if (msg.substring(matcher.start()).startsWith("%g"))
						solvedMsg.append(triggerAttr[3]);
					else if (msg.substring(matcher.start()).startsWith("%1"))
						solvedMsg.append(triggerAttr[4]);
					else if (msg.substring(matcher.start()).startsWith("%2"))
						solvedMsg.append(triggerAttr[5]);
					else if (msg.substring(matcher.start()).startsWith("%3"))
						solvedMsg.append(triggerAttr[6]);
					else if (msg.substring(matcher.start()).startsWith("%4"))
						solvedMsg.append(triggerAttr[7]);
					else if (msg.substring(matcher.start()).startsWith("%5"))
						solvedMsg.append(triggerAttr[8]);
					else if (msg.substring(matcher.start()).startsWith("%c"))
						solvedMsg.append(triggerAttr[9]);
			}

			solvedMsg.append(msg.substring(newContentIndex));
			message2 = solvedMsg.toString();
			return solvedMsg.toString();
		} else {
			return "";
		}
	}

	public Pattern getPattern() {
		if (pattern == null)
			pattern = Pattern.compile(regex);
		return pattern;
	}

	public Matcher getMatcher(String str) {
		return getPattern().matcher(str);
	}

	public String getTitle() {
		return title;
	}

	public void setTitle(String title) {
		this.title = title;
	}

	public String getRegex() {
		return regex;
	}

	public String getReact() {
		return react;
	}

	public void setRegex(String regex) {
		pattern = null;
		this.regex = regex;
	}

	public void setReact(String react) {
		pattern = null;
		this.react = react;
	}

	public String getReactDo() {
		return reactDo;
	}

	public String getServerMsg() {
		return serverMsg;
	}

	public void setServerMsg(String serverMsg) {
		this.serverMsg = serverMsg;
	}

	public int getServerMsgSize() {
		return serverMsgSize;
	}

	public void setServerMsgSize(int serverMsgSize) {
		this.serverMsgSize = serverMsgSize;
	}

	public Color getServerMsgColor() {
		return serverMsgColor;
	}

	public void setServerMsgColor(Color serverMsgColor) {
		this.serverMsgColor = serverMsgColor;
	}

	public int getIgnoreTimer() {
		return ignoreTimer;
	}

	public void setIgnoreTimer(int ignoreTimer) {
		this.ignoreTimer = ignoreTimer;
	}

	public int getTimerPeriod() {
		return timerPeriod;
	}

	public void setTimerPeriod(int timerPeriod) {
		this.timerPeriod = timerPeriod;
	}

	public int getTimerWarning() {
		return timerWarning;
	}

	public void setTimerWarning(int timerWarning) {
		this.timerWarning = timerWarning;
	}

	public String getTimerWarningMsg() {
		return timerWarningMsg;
	}

	public void setTimerWarningMsg(String timerWarningMsg) {
		this.timerWarningMsg = timerWarningMsg;
	}

	public int getTimerWarningMsgSize() {
		return timerWarningMsgSize;
	}

	public void setTimerWarningMsgSize(int timerWarningMsgSize) {
		this.timerWarningMsgSize = timerWarningMsgSize;
	}

	public Color getTimerWarningMsgColor() {
		return timerWarningMsgColor;
	}

	public void setTimerWarningMsgColor(Color timerWarningMsgColor) {
		this.timerWarningMsgColor = timerWarningMsgColor;
	}

	public String getTimerWarningSound() {
		return timerWarningSound;
	}

	public void setTimerWarningSound(String timerWarningMsgSound) {
		timerWarningSound = timerWarningMsgSound;
	}

	public int getTimerRemove() {
		return timerRemove;
	}

	public void setTimerRemove(int timerRemove) {
		this.timerRemove = timerRemove;
	}

	public boolean isActive() {
		return active;
	}

	public void setActive(boolean active) {
		this.active = active;
	}

	public int getQuantity() {
		return quantity;
	}

	public void setQuantity(int quantity) {
		this.quantity = quantity;
	}

	public boolean isServerMsgActive() {
		return serverMsgActive;
	}

	public void setServerMsgActive(boolean serverMsgActive) {
		this.serverMsgActive = serverMsgActive;
	}

	public boolean isSoundActive() {
		return soundActive;
	}

	public void setSoundActive(boolean soundActive) {
		this.soundActive = soundActive;
	}

	public String getSound() {
		return sound;
	}

	public void setSound(String sound) {
		this.sound = sound;
	}

	public void setTimerActive(boolean timerActive) {
		this.timerActive = timerActive;
	}

	public boolean isTimerActive() {
		return timerActive;
	}

	public boolean isTimerShow1() {
		return timerShow1;
	}

	public void setTimerShow1(boolean timerShow1) {
		this.timerShow1 = timerShow1;
	}

	public boolean isTimerShow2() {
		return timerShow2;
	}

	public void setTimerShow2(boolean timerShow2) {
		this.timerShow2 = timerShow2;
	}

	public boolean isTimerShow3() {
		return timerShow3;
	}

	public void setTimerShow3(boolean timerShow3) {
		this.timerShow3 = timerShow3;
	}

	public void setTimerShow3Fault(boolean timerShow3) {
		this.timerShow3 = false;
	}

	public long getFirstTriggerTime() {
		return firstTriggerTime;
	}

	public void setFirstTriggerTime(long lastTriggerTime) {
		firstTriggerTime = lastTriggerTime;
	}

	public int getTriggerCount() {
		return triggerCount;
	}

	public void setTriggerCount(int triggerCount) {
		this.triggerCount = triggerCount;
	}

	public void increaseTriggerCount() {
		triggerCount++;
	}

	public int getId() {
		return id;
	}

	public void setId(int id) {
		this.id = id;
	}

	public String getCategory() {
		return category;
	}

	public void setCategory(String category) {
		this.category = category;
	}

	public void clearAttrStrings() {
		attrStrings.clear();
	}

	public void addAttrString(String attrStr) {
		attrStrings.add(attrStr);
	}

	public boolean containsAttrString(String attrStr) {
		return attrStrings.contains(attrStr);
	}

	public String getSolvedServerMsg() {
		return solvedServerMessage;
	}

	public String getSolvedTimerWarningMessage() {
		return solvedTimerWarningMessage;
	}

	public String getGlobLogLine() {
		return globLine;
	}

	public void setGlobLogLine(String Line) {
		globLine = Line;
	}

	public void setCharName(String Line) {
		CharName = Line;
	}

	public String getCharName() {
		return CharName;
	}

	public boolean getPrivatSound() {
		return privatSound;
	}

	public void setPrivatSound(boolean set) {
		privatSound = set;
	}

	public static final String NO_CATEGORY = "";
	public static final String NO_SOUND = "<kein>";
	int id;
	String title;
	boolean active;
	String category;
	String regex;
	String react;
	String reactDo;
	int quantity;
	int ignoreTimer;
	boolean serverMsgActive;
	String serverMsg;
	int serverMsgSize;
	Color serverMsgColor;
	boolean soundActive;
	String sound;
	boolean timerActive;
	boolean timerShow1;
	boolean timerShow2;
	boolean timerShow3;
	boolean privatSound;
	int timerPeriod;
	int timerWarning;
	String timerWarningMsg;
	int timerWarningMsgSize;
	Color timerWarningMsgColor;
	String timerWarningSound;
	int timerRemove;
	Pattern pattern;
	long firstTriggerTime;
	int triggerCount;
	public String message;
	public String message2;
	String solvedServerMessage;
	String solvedTimerWarningMessage;
	HashSet attrStrings;
	boolean globSoundCheck;
	String globLine;
	String CharName;
	private static final String VAR_USER = "%u";
	private static final String VAR_SPELL = "%s";
	private static final String VAR_ATTACKER = "%a";
	private static final String VAR_TARGET = "%t";
	private static final String VAR_TARGETS_GROUP = "%g";
	private static final String VAR_CHAR = "%c";
	private static final String VAR_T1 = "%1";
	private static final String VAR_T2 = "%2";
	private static final String VAR_T3 = "%3";
	private static final String VAR_T4 = "%4";
	private static final String VAR_T5 = "%5";
	private static final Pattern CUSTOM_VAR_PATTERN = Pattern.compile("(%u|%s|%a|%t|%g|%1|%2|%3|%4|%5|%c)");

}

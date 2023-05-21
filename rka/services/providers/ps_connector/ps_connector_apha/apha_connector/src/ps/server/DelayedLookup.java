// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   DelayedLookup.java

package ps.server;

public abstract class DelayedLookup implements Runnable {

	public DelayedLookup(int delay) {
		running = true;
		this.delay = 1000;
		this.delay = delay;
	}

	@Override
	public void run() {
		try {
			while (running) {
				Thread.sleep(delay);
				lookupNow();
			}
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	protected abstract void lookupNow();

	public void stop() {
		running = false;
	}

	private boolean running;
	private int delay;
}

// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   PacketContent.java

package ps.net;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public interface PacketContent {

	public abstract void writeContent(OutputStream outputstream) throws IOException;

	public abstract void readContent(InputStream inputstream) throws IOException;
}

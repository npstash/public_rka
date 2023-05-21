// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   MD5.java

package ps.util;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public class MD5 {

	public MD5(byte md5Bytes[]) {
		this.md5Bytes = md5Bytes;
	}

	public byte[] getBytes() {
		return md5Bytes;
	}

	@Override
	public boolean equals(Object o) {
		boolean ret = false;
		if (o != null && (o instanceof MD5)) {
			byte oBytes[] = ((MD5) o).getBytes();
			if (oBytes != null && oBytes.length == md5Bytes.length) {
				ret = true;
				for (int i = 0; i < oBytes.length; i++) {
					if (oBytes[i] == md5Bytes[i])
						continue;
					ret = false;
					break;
				}

			}
		}
		return ret;
	}

	public static byte[] generateAuthId(String userName, String password) {
		byte ret[] = new byte[16];
		try {
			MessageDigest messageDigest = MessageDigest.getInstance("MD5");
			String str = (new StringBuilder(String.valueOf(userName))).append(password).toString();
			messageDigest.update(str.getBytes());
			ret = messageDigest.digest();
		} catch (NoSuchAlgorithmException ex) {
			ex.printStackTrace();
		}
		return ret;
	}

	byte md5Bytes[];
}

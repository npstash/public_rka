// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   User.java

package ps.server.rights;

import ps.util.MD5;

public class User {

	public User() {
		right = 0;
	}

	public User(String name, MD5 authId) {
		right = 0;
		this.name = name;
		this.authId = authId;
	}

	public User(String name, String pass) {
		right = 0;
		this.name = name;
		authId = new MD5(MD5.generateAuthId(name, pass));
	}

	@Override
	public String toString() {
		return name;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public MD5 getAuthId() {
		return authId;
	}

	public void setAuthId(MD5 authId) {
		this.authId = authId;
	}

	public boolean isAdmin() {
		return right == 1;
	}

	public void setAdmin(boolean b) {
		right = b ? 1 : 0;
	}

	public void setRight(int right) {
		this.right = right;
	}

	public int getRight() {
		return right;
	}

	public static final int RIGHT_NONE = 0;
	public static final int RIGHT_ADMIN = 1;
	String name;
	MD5 authId;
	int right;
}

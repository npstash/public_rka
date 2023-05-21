// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   RightsManager.java

package ps.server.rights;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.Iterator;
import java.util.Vector;

import ps.util.MD5;

// Referenced classes of package ps.server.rights:
//            User

public class RightsManager {

	public RightsManager() {
		defAdminUser = new User("Admin", "");
		userList = new Vector();
		load();
		if (Boolean.parseBoolean(System.getProperty("DefaultAdmin", "false"))) {
			User adminUser = getUserByName(defAdminUser.getName());
			if (adminUser != null)
				userList.remove(adminUser);
			defAdminUser.setAdmin(true);
			userList.add(defAdminUser);
		}
		if (userList.size() == 0) {
			defAdminUser.setAdmin(true);
			userList.add(defAdminUser);
		}
	}

	public void addUser(User user) {
		if (!existsUserName(user.getName())) {
			userList.add(user);
			save();
		}
	}

	public void removeUser(String userName) {
		User userToDelete = getUserByName(userName);
		if (userToDelete != null) {
			userList.remove(userToDelete);
			save();
		}
	}

	public User getUserWithAuthId(MD5 authId) {
		for (Iterator iterator = userList.iterator(); iterator.hasNext();) {
			User user = (User) iterator.next();
			if (user.getAuthId().equals(authId))
				return user;
		}

		return null;
	}

	public boolean existsUserName(String userName) {
		for (Iterator iterator = userList.iterator(); iterator.hasNext();) {
			User user = (User) iterator.next();
			if (user.getName().equalsIgnoreCase(userName))
				return true;
		}

		return false;
	}

	public User getUserByName(String userName) {
		for (Iterator iterator = userList.iterator(); iterator.hasNext();) {
			User user = (User) iterator.next();
			if (user.getName().equals(userName))
				return user;
		}

		return null;
	}

	public void save() {
		try {
			FileOutputStream out = new FileOutputStream(SAVE_FILE_NAME);
			out.write(userList.size());
			User user;
			for (Iterator iterator = userList.iterator(); iterator.hasNext(); out
					.write(user.getName().getBytes("Cp1250"))) {
				user = (User) iterator.next();
				out.write(user.getAuthId().getBytes());
				out.write(user.getRight());
				out.write(user.getName().length());
			}

			out.flush();
			out.close();
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	private void load() {
		try {
			if ((new File(SAVE_FILE_NAME)).exists()) {
				FileInputStream in = new FileInputStream(SAVE_FILE_NAME);
				int userCount = in.read();
				for (int i = 0; i < userCount; i++) {
					User user = new User();
					byte authId[] = new byte[16];
					in.read(authId);
					user.setAuthId(new MD5(authId));
					user.setRight(in.read());
					byte userNameBytes[] = new byte[in.read()];
					in.read(userNameBytes);
					user.setName(new String(userNameBytes, "Cp1250"));
					userList.add(user);
				}

				in.close();
			}
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	public static final String KEY_DEFAULT_ADMIN = "DefaultAdmin";
	private static String SAVE_FILE_NAME = "users.bin";
	User defAdminUser;
	Vector userList;

}

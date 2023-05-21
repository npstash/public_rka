// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   ClientManager.java

package ps.server;

import java.util.TreeMap;
import java.util.Vector;

import ps.server.net.ClientInfo;

public class ClientManager {

	public ClientManager() {
		clientListLock = new Object();
		clientInfos = new ClientInfo[0];
		clientList = new Vector(50);
	}

	private ClientInfo[] createClientInfoArray() {
		return (ClientInfo[]) clientList.toArray(new ClientInfo[clientList.size()]);
	}

	public ClientInfo[] getAllClientInfos() {
		return clientInfos;
	}

	public void addClient(ClientInfo clientInfo) {
		synchronized (clientListLock) {
			clientList.add(clientInfo);
			clientInfos = createClientInfoArray();
		}
	}

	public void removeClientInfo(ClientInfo clientInfo) {
		clientInfo.close();
		synchronized (clientListLock) {
			clientList.remove(clientInfo);
			clientInfos = createClientInfoArray();
		}
	}

	public ClientInfo getClientInfoByUserName(String userName) {
		synchronized (clientListLock) {
			int i;
			int j;
			ClientInfo aclientinfo[];
			j = (aclientinfo = clientInfos).length;
			i = 0;

			while (i < j) {
				ClientInfo clientInfo = aclientinfo[i];
				i++;
				if (clientInfo.getUser() == null || !clientInfo.getUser().getName().equals(userName))
					continue; /* Loop/switch isn't completed */
				return clientInfo;
			}
		}
		return null;
	}

	public ClientInfo[] getClientInfosSortedByUserName() {
		ClientInfo ret[];
		synchronized (clientListLock) {
			TreeMap userNameToClientMap = new TreeMap();
			ClientInfo aclientinfo[];
			int j = (aclientinfo = clientInfos).length;
			for (int i = 0; i < j; i++) {
				ClientInfo clientInfo = aclientinfo[i];
				if (clientInfo.getUser() != null)
					userNameToClientMap.put(clientInfo.getUser().getName(), clientInfo);
			}

			ret = (ClientInfo[]) userNameToClientMap.values().toArray(new ClientInfo[userNameToClientMap.size()]);
		}
		return ret;
	}

	Object clientListLock;
	private ClientInfo clientInfos[];
	private Vector clientList;
}

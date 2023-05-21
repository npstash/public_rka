// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   PsServerSocket.java

package ps.server.net;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;

import ps.server.ServerPacketHandler;

// Referenced classes of package ps.server.net:
//            ClientInfo

public class PsServerSocket extends Thread {

	public PsServerSocket(ServerPacketHandler serverPacketHandler) {
		super("PsServerSocket");
		buffer = new byte[51200];
		running = true;
		this.serverPacketHandler = serverPacketHandler;
	}

	public void open(int port) throws IOException {
		serverSocket = new ServerSocket();
		serverSocket.setPerformancePreferences(0, 1, 0);
		serverSocket.bind(new InetSocketAddress(port));
		UpdaterServerSocket1 = new ServerSocket(53730);
		UpdaterServerSocket1.setPerformancePreferences(0, 1, 0);
		UpdaterServerSocket2 = new ServerSocket(53731);
		UpdaterServerSocket2.setPerformancePreferences(0, 1, 0);
		UpdaterServerSocket3 = new ServerSocket(53732);
		UpdaterServerSocket3.setPerformancePreferences(0, 1, 0);
		UpdaterServerSocket4 = new ServerSocket(53734);
		UpdaterServerSocket4.setPerformancePreferences(0, 1, 0);
		start();
	}

	public void close() {
		running = false;
		try {
			serverSocket.close();
		} catch (IOException ex) {
			ex.printStackTrace();
		}
	}

	@Override
	public void run() {
		while (running)
			try {
				Socket socket = serverSocket.accept();
				socket.setTcpNoDelay(true);
				System.out.println((new StringBuilder("Connection accepted from: ")).append(socket).toString());
				ClientInfo clientInfo = new ClientInfo(socket, serverPacketHandler);
				clientInfo.open();
				serverPacketHandler.getClientManager().addClient(clientInfo);
				sleep(200L);
			} catch (Exception ex) {
				if (running)
					ex.printStackTrace();
			} catch (OutOfMemoryError error) {
				System.out.println((new StringBuilder("OUT OF MEMORY: ")).append(error.getMessage()).toString());
				System.gc();
				try {
					sleep(5000L);
				} catch (InterruptedException ex) {
					ex.printStackTrace();
				}
			}
	}

	public void Updater(int n) throws Exception {
		if (n == 0 || n == 1) {
			Socket clientUpdate1 = UpdaterServerSocket1.accept();
			BufferedInputStream in = new BufferedInputStream(new FileInputStream("sounds.zip"));
			BufferedOutputStream out = new BufferedOutputStream(clientUpdate1.getOutputStream());
			for (int len = 0; (len = in.read(buffer)) > 0;) {
				out.write(buffer, 0, len);
				System.out.println((new StringBuilder("Buffer size: ")).append(len).append("bytes / ").toString());
			}

			in.close();
			out.flush();
			out.close();
			clientUpdate1.close();
			System.out.println("Sende sounds");
		}
		if (n == 0) {
			System.out.println("Sende Apha-PS_lib");
			Socket clientUpdate4 = UpdaterServerSocket4.accept();
			BufferedInputStream in = new BufferedInputStream(new FileInputStream("Apha-PS_lib.zip"));
			BufferedOutputStream out = new BufferedOutputStream(clientUpdate4.getOutputStream());
			for (int len = 0; (len = in.read(buffer)) > 0;) {
				System.out.println((new StringBuilder("Buffer size: ")).append(len).append("bytes / ").toString());
				out.write(buffer, 0, len);
			}

			in.close();
			out.flush();
			out.close();
			clientUpdate4.close();
			System.out.println("Sende Apha-PS_lib");
		}
		if (n == 0 || n == 2) {
			Socket clientUpdate2 = UpdaterServerSocket2.accept();
			BufferedInputStream in = new BufferedInputStream(new FileInputStream("ptrigger.bin"));
			BufferedOutputStream out = new BufferedOutputStream(clientUpdate2.getOutputStream());
			for (int len = 0; (len = in.read(buffer)) > 0;) {
				out.write(buffer, 0, len);
				System.out.println((new StringBuilder("Buffer size: ")).append(len).append("bytes / ").toString());
			}

			in.close();
			out.flush();
			out.close();
			clientUpdate2.close();
			System.out.println("\nDone! - 1");
		}
		if (n == 0 || n == 3) {
			Socket clientUpdate3 = UpdaterServerSocket3.accept();
			BufferedInputStream in = new BufferedInputStream(new FileInputStream("Apha-PS.jar"));
			BufferedOutputStream out = new BufferedOutputStream(clientUpdate3.getOutputStream());
			int len = 0;
			System.out.println("sende Update(3) - Client");
			while ((len = in.read(buffer)) > 0) {
				System.out.println((new StringBuilder("Buffer size: ")).append(len).append("bytes / ").toString());
				out.write(buffer, 0, len);
			}
			in.close();
			out.flush();
			out.close();
			clientUpdate3.close();
			System.out.println("sende Update(3) - Client - done");
		}
	}

	public static final int DEF_SERVER_PORT = 53729;
	public static final int DEF_UPDATE_SERVER_PORT1 = 53730;
	public static final int DEF_UPDATE_SERVER_PORT2 = 53731;
	public static final int DEF_UPDATE_SERVER_PORT3 = 53732;
	public static final int DEF_UPDATE_SERVER_PORT4 = 53734;
	public static final int BUFFER_SIZE = 51200;
	private byte buffer[];
	boolean running;
	ServerSocket serverSocket;
	ServerSocket UpdaterServerSocket1;
	ServerSocket UpdaterServerSocket2;
	ServerSocket UpdaterServerSocket3;
	ServerSocket UpdaterServerSocket4;
	ServerPacketHandler serverPacketHandler;
}

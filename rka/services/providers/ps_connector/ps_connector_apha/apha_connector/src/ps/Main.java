// Decompiled by Jad v1.5.8g. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 
// Source File Name:   Test.java

package ps;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;

import ps.client.net.ClientPacketHandler;
import ps.net.Packet;

public class Main implements Runnable {
    public static final String PREFIX_SENDING = "SENDING:";
    public static final String PREFIX_INPUT = "INPUT:";
    public static final String PREFIX_RECEIVED = "RECEIVED:";

    class PipeReader implements Runnable {
        @Override
        public void run() {
            BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
            try {
                while (Main.this.is_connector_running()) {
                    Main.this.read_command(br);
                }
                br.close();
            } catch (IOException e) {
            }
        }
    }

    private boolean running = false;

    ClientPacketHandler packetHandler = new ClientPacketHandler() {
        protected void firePacketRecieved(ps.net.Packet packet1) {
            if (packet1.isTypeOf(Packet.TYPE_CLIENT_INFO))
                return;
//            if (packet1.isTypeOf(Packet.TYPE_TRIGGER_DESC))
//                return;
            System.out.println(Main.PREFIX_RECEIVED + packet1.toString());
        };
    };

    public Main() {
    }

    @Override
    public void run() {
        this.running = true;
        new Thread(new Main.PipeReader()).start();
    }

    public void read_command(BufferedReader reader) throws IOException {
        String command = reader.readLine();
        System.out.println(Main.PREFIX_INPUT + command);
        switch (command) {
        case "LOGIN": {
            String server_address = reader.readLine();
            int port;
            try {
                port = Integer.parseInt(reader.readLine());
            } catch (Exception e) {
                break;
            }
            String username = reader.readLine();
            String password = reader.readLine();
            this.packetHandler.login(server_address, port, username, password);
        }
            break;
        case "QUIT": {
            this.running = false;
            this.packetHandler.close();
        }
            break;
        case "TRIGGER_EVENT": {
            int id;
            try {
                id = Integer.parseInt(reader.readLine());
            } catch (Exception e) {
                break;
            }
            String trigger_data = reader.readLine();
            this.packetHandler.sendTriggerEvent(id, trigger_data);
        }
            break;
        }
    }

    public boolean is_connector_running() {
        return this.running;
    }

    public static void main(String args[]) throws Exception {
        Main main = new Main();
        main.run();
    }
}

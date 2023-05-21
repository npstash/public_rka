package ps;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;

public class CmdTest {
    public static void main(String[] args) throws IOException {
        while (true) {
            System.out.println("CmdTest.main()");
            BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
            String line = br.readLine();
            System.out.println("I've read: " + line);
        }

    }
}

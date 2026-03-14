using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class test : MonoBehaviour
{
 
    private string lastTag = ""; 
    private string command = "";
    private float velocity = 0;
    private UdpClient udpClient;
    public string serverIP = "192.168.4.1"; 
    public float sendInterval = 0.01f; 
    private DateTime lastSendTime;
    private DateTime lastReceiveTime;
    private double roundTripTime = 0.01f; 
    private float exitDebounceTime = 0.150f;
    private bool debounceExit = false;
    private float exitTime = 0f;
    public float surfaceHeight = 0.0f; 
    public float lockThreshold = 0.05f; 
    public float releaseThreshold = 0.1f;
    private bool isGrounded = false; 
    private bool isSliding = false; 
    public int serverPort = 12345;
    public Camera mainCamera;


    void Start()
    {

        if (mainCamera == null)
        {
            mainCamera = Camera.main; 
        }

        try
        {
            udpClient = new UdpClient();
            udpClient.Connect(serverIP, serverPort);
            udpClient.BeginReceive(new AsyncCallback(ReceiveCallback), null);
            SendUDPData("Hello", "hi", 0, false);
        }
        catch (Exception e)
        {
            Debug.LogError("Failed to initialize UDP client: " + e.Message);
        }
    }


    private void Update()
    {
        Ray ray = mainCamera.ScreenPointToRay(Input.mousePosition);
        RaycastHit hit;

        if (Physics.Raycast(ray, out hit))
        {
            string objectTag = hit.collider.gameObject.tag;
            if (Input.GetMouseButtonDown(0)) 
            {
                SendUDPData("enter", objectTag, 2, false); 
                Debug.Log($"Simulated Enter Command Sent for Tag: {objectTag}");
            }

            if (Input.GetMouseButton(0))
            {
                SendUDPData("stay", objectTag, 2, false);
                Debug.Log($"Simulated Stay Command Sent for Tag: {objectTag}");
            }

      
            if (Input.GetMouseButtonDown(1))  
            {
                SendUDPData("exit", objectTag, 0, false);
                Debug.Log($"Simulated Exit Command Sent for Tag: {objectTag}");
            }
        }

    }

    private void CloseUDPClient()
    {
        if (udpClient != null)
        {
            udpClient.Close();
            udpClient = null;
            Debug.Log("UDP client closed.");
        }
    }

    private void SendUDPData(string command, string textureTag, float velocity, bool modulation)
    {
        if (udpClient != null)
        {
            try
            {
                string modulationState = modulation.ToString().ToLower();
                long timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                string message = $"{command},{textureTag},{velocity},{modulationState}";
                byte[] data = Encoding.UTF8.GetBytes(message);
                udpClient.Send(data, data.Length);
        
            }
            catch (Exception e)
            {
                Debug.LogError("Failed to send UDP data: " + e.Message);
            }
        }
    }

    private void ReceiveCallback(IAsyncResult ar)
    {
        if (udpClient == null) return;

        try
        {
            IPEndPoint endPoint = new IPEndPoint(IPAddress.Any, 0);
            byte[] data = udpClient.EndReceive(ar, ref endPoint);
            string receivedMessage = Encoding.UTF8.GetString(data);

            string[] parts = receivedMessage.Split(',');
            if (parts.Length != 4)
            {
                Debug.LogError("Received message has incorrect format.");
                return;
            }

            string receivedCommand = parts[0];
            string receivedTextureTag = parts[1];
            if (!float.TryParse(parts[2], out float receivedVelocity))
            {
                Debug.LogError("Failed to parse velocity from received message.");
                return;
            }

            if (!bool.TryParse(parts[3], out bool receivedModulation ))
            {
                Debug.LogError("Failed to parse modulation state from received message.");
                return;
            }

           
            udpClient.BeginReceive(new AsyncCallback(ReceiveCallback), null);
        }
        catch (Exception e)
        {
            Debug.LogError("Failed to receive UDP data: " + e.Message);
        }
    }

    bool ValidTag(string tag)
    {
        return tag == "1" || tag == "2" || tag == "3" || tag == "4" ||
               tag == "5" || tag == "6" || tag == "7" || tag == "8" ||
               tag == "9" || tag == "10" || tag == "11" || tag == "12" ||
               tag == "13" || tag == "14" || tag == "15" || tag == "16" ||
               tag == "17" || tag == "18" || tag == "19" || tag == "20" ||
               tag == "21" || tag == "22" || tag == "23" || tag == "24" ||
               tag == "25" || tag == "26" || tag == "27" || tag == "28" ||
               tag == "29" || tag == "30" || tag == "31" || tag == "32";
    }

    
    private void OnApplicationQuit()
    {
        CloseUDPClient();
    }

    private void OnDestroy()
    {
        CloseUDPClient();
    }
}


/*tag == "4_megalo" || tag == "4_mikro" || tag == "4_sandpaper" || tag == "5_megalo" || tag == "5_mikro" || tag == "5_sandpaper" ||
               tag == "7_megalo" || tag == "7_mikro" || tag == "7_sandpaper" || tag == "8_megalo" || tag == "8_mikro" || tag == "8_sandpaper" ||
               tag == "10_megalo" || tag == "10_mikro" || tag == "10_sandpaper" || tag == "11_megalo" || tag == "11_mikro" || tag == "11_sandpaper" ||
               tag == "14_megalo" || tag == "14_mikro" || tag == "14_sandpaper" || tag == "15_megalo" || tag == "15_mikro" || tag == "15_sandpaper" ||
               tag == "16_megalo" || tag == "16_mikro" || tag == "16_sandpaper" || tag == "20_megalo" || tag == "20_mikro" || tag == "20_sandpaper" ||
               tag == "26_megalo" || tag == "26_mikro" || tag == "26_sandpaper" || tag == "27_megalo" || tag == "27_mikro" || tag == "27_sandpaper";
        */
using System;
using System.Collections;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class FingertipColliderManager : MonoBehaviour
{
    public Collider fingertipCollider;
    public Rigidbody fingertipRigidbody;
    private bool isColliding = false; //debouncing flag
    private string lastTag = ""; //track the last sent tag
    private string command = "";
    private float velocity = 0;

    private UdpClient udpClient;
    public string serverIP = "192.168.4.1"; //ESP32-S3 IP address
    public int serverPort = 12345; //ESP32-S3 UDP port
    private bool isConnected = true; 
    private float reconnectInterval = 5.0f; 
    private Coroutine reconnectCoroutine;
    public float sendInterval = 0.005f; //interval between sends in seconds 
    private float nextSendTime;
    private DateTime lastSendTime;
    private DateTime lastReceiveTime;
    private double roundTripTime = 0.01f; //initial RTT in seconds
    private float exitDebounceTime = 0.150f; //debounce time
    private bool debounceExit = false;
    private float exitTime = 0f;

    public float surfaceHeight = 0.0f; //Y position of the surface
    public float lockThreshold = 0.05f; 
    public float releaseThreshold = 0.1f; 

    private bool isGrounded = false; 
    private bool isSliding = false; 

    private float lastInteractionTime = 0f;
    public Camera_Movement cameraMovement;



    void Start()
    {
        //Application.targetFrameRate = 90; 
        fingertipCollider = GetComponent<Collider>();
        fingertipRigidbody = GetComponent<Rigidbody>();

        if (fingertipCollider == null || fingertipRigidbody == null)
        {
            Debug.LogError("Collider or Rigidbody not found on fingertip.");
            return;
        }
        InitializeUDPClient();
    }

    public void Initialize(Camera_Movement cameraMovementReference)
    {
        cameraMovement = cameraMovementReference;

        if (cameraMovement == null)
        {
            Debug.LogError("Camera_Movement reference is null. Ensure it is set correctly.");
        }
    }


    private void InitializeUDPClient()
    {
        try
        {
            udpClient = new UdpClient();
            udpClient.Connect(serverIP, serverPort);
            udpClient.BeginReceive(new AsyncCallback(ReceiveCallback), null);
            SendUDPData("Hello", "hi", 0);
            isConnected = true;
            Debug.Log("UDP client initialized and connected.");
        }
        catch (Exception e)
        {
            Debug.LogError("Failed to initialize UDP client: " + e.Message);
            HandleDisconnection();
        }
    }


    private void HandleDisconnection()
    {
        isConnected = false;
        CloseUDPClient();

        if (reconnectCoroutine == null)
        {
            reconnectCoroutine = StartCoroutine(TryReconnect());
        }
    }

    private IEnumerator TryReconnect()
    {
        while (!isConnected)
        {
            Debug.Log("Attempting to reconnect..");

            try
            {
                InitializeUDPClient();
            }
            catch (Exception e)
            {
                Debug.LogError("Reconnection attempt failed: " + e.Message);
            }

            yield return new WaitForSeconds(reconnectInterval);
        }

        reconnectCoroutine = null; //stop the coroutine once reconnected
    }



    private void Update()
    {
        Vector3 fingertipPosition = fingertipRigidbody.transform.position;
        Vector3 fingertipColPosition = fingertipCollider.transform.position;

        float distanceToSurface = Mathf.Abs(fingertipPosition.y - surfaceHeight);
        float distanceToSurfaceCol = Mathf.Abs(fingertipColPosition.y - surfaceHeight);

        //check if the hand is grounded on the surface 
        if (distanceToSurface < lockThreshold && !isSliding)
        {
            isGrounded = true;
            isSliding = true;
            Debug.Log("Hand is grounded. Y-axis locked to surface.");
        }

        //lock the Y-axis to the surface height for smooth sliding
        if (isGrounded)
        {
            Vector3 slidingPosition = new Vector3(fingertipPosition.x, surfaceHeight, fingertipPosition.z);
            Vector3 slidingPositionCol = new Vector3(fingertipColPosition.x, surfaceHeight, fingertipColPosition.z);

            fingertipRigidbody.MovePosition(slidingPosition); 
            fingertipCollider.transform.position = slidingPositionCol;
        }

        if (fingertipPosition.y > surfaceHeight + releaseThreshold && isSliding)
        {
            isGrounded = false;
            isSliding = false;
            surfaceHeight = 0.0f;
            Debug.Log("Hand lifted. Y-axis unlocked.");
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

    private void SendUDPData(string command, string textureTag, float velocity)
    {
        if (udpClient != null)
        {
            try
            {
             
                bool modulationState = cameraMovement != null && cameraMovement.GetToggleState();    //bool to lowercase string
                string message = $"{command},{textureTag},{velocity},{modulationState.ToString().ToLower()}";
                byte[] data = Encoding.UTF8.GetBytes(message);
                udpClient.Send(data, data.Length);
                Debug.Log($"Sent: {message} at {Time.time}");
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

            //Debug.Log("Received: " + receivedMessage);
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

            if (!bool.TryParse(parts[3], out bool receivedModulation))
            {
                Debug.LogError("Failed to parse modulation state from received message.");
                return;
            }

            if (!isConnected)
            {
                Debug.Log("Connection restored.");
                isConnected = true;

                if (reconnectCoroutine != null)
                {
                    StopCoroutine(reconnectCoroutine);
                    reconnectCoroutine = null;
                }
            }
            //AdjustSendInterval(receivedTimestamp);
            udpClient.BeginReceive(new AsyncCallback(ReceiveCallback), null);
        }
        catch (Exception e)
        {
            Debug.LogError("Failed to receive UDP data: " + e.Message);
            HandleDisconnection();
        }
    }

    private void AdjustSendInterval(long receivedTimestamp)
    {
        long currentTime = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        long rtt = currentTime - receivedTimestamp;
        sendInterval = Mathf.Clamp(0.01f + (rtt / 1000.0f), 0.01f, 0.1f);  //adjust dynamically based on RTT
        Debug.Log($"Adjusted send interval to {sendInterval} seconds based on RTT {rtt} ms");
    }

    bool ValidTag(string tag)
    {
        return tag == "1" || tag == "2" || tag == "3" || tag == "4" ||
               tag == "5" || tag == "6" || tag == "7" || tag == "8" ||
               tag == "9" || tag == "10" || tag == "11" || tag == "12" ||
               tag == "13" || tag == "14" || tag == "15" || tag == "16" ||
               tag == "17" || tag == "18";
    }

    void OnCollisionEnter(Collision collision)
    {
        if (fingertipCollider == null ) return; 
        if (ValidTag(collision.gameObject.tag))
        {
            foreach (ContactPoint contact in collision.contacts)
            {
                if (IsBottomPartCollision(contact.point))
                {
                    surfaceHeight = collision.contacts[0].point.y; //capture the surface height from the collision point
                    isGrounded = true;
                    //Debug.Log($"Collision Enter detected with {collision.gameObject.tag}. Surface height set to {surfaceHeight}");
                    if (!isColliding) //only trigger enter if not already in a collision
                    {
                        Debug.Log("ENTER");
                        SendUDPData("enter", collision.gameObject.tag, 0);
                        isColliding = true;
                        command = "enter";
                        lastTag = collision.gameObject.tag;
                        velocity = 0;
                    }
                    break; //exit after detecting valid collision
                }
            }
        }
    }

    void OnCollisionStay(Collision collision)
    {
        if (fingertipCollider == null) return; 

        if (ValidTag(collision.gameObject.tag))
        {
            foreach (ContactPoint contact in collision.contacts)
            {
                if (IsBottomPartCollision(contact.point))
                {
                    Debug.Log("STAY");
                    float xVelocity = fingertipRigidbody.velocity.x;
                    if (xVelocity <= 0.05f)
                    {
                        return;
                    }
                    if (Time.time >= nextSendTime)
                    {
                       SendUDPData("stay", collision.gameObject.tag, Mathf.Abs(xVelocity));
                       nextSendTime = Time.time + sendInterval;  //update next send time based on sendInterval
                    }
                    isColliding = true;
                    command = "stay";
                    lastTag = collision.gameObject.tag;
                    break; 
                }
            }
        }
    }
    void OnCollisionExit(Collision collision)
    {

        if (ValidTag(collision.gameObject.tag))
        {

            isGrounded = false; //release the lock when the hand leaves the surface
            isSliding = false;
            Debug.Log($"EXIT: Collision exit detected with object: {collision.gameObject.tag}");
            //set a time to debounce exit events to avoid immediate re-entering
            exitTime = Time.time + exitDebounceTime;
            debounceExit = true; 
            surfaceHeight = 0.0f; //reset surface height after exit
            SendUDPData("exit", "0", 0);
            isColliding = false;
            command = "exit";
            lastTag = ""; 
        }
    }
    bool IsBottomPartCollision(Vector3 contactPoint)
    {
        Vector3 localContactPoint = transform.InverseTransformPoint(contactPoint); //transform the contact point to local space of the fingertip
        return localContactPoint.y < -0.005f; //bottom part is in the negative Y direction in local space
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

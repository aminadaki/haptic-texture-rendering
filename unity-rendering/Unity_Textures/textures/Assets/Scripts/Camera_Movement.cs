using System;
using System.Collections;
using System.Collections.Generic;
//using System.Diagnostics;
using UnityEngine;
using UnityEngine.UI;
using Leap.Unity;
using UnityEngine.EventSystems;

public class Camera_Movement : MonoBehaviour
{
    public Camera mainCamera;
    public LeapServiceProvider leapProvider;
    public Button audioButton;
    public Button accelButton;
    public Button comboButton;
    private Button currentButton;
    private Button previousButton;
    private Color newColor = new Color(255,255,255);
    private ColorBlock cb;

    public SetSelectedGameObject selectObj;

    public GameObject small_comb;
    public GameObject sandpaper;
    public GameObject big_comb;

    public GameObject audioDropDown;
    public GameObject accelDropDown;
    public GameObject comboDropDown;
    public Boolean velocityFeatureOn = true;
    public Toggle velocityFeatureButton;
    public Vector3 leapProviderOffset = new Vector3(0f, -0.02f, 0.01f);

    void Start()
    {
        //cb = audioButton.colors;
        //cb.normalColor = newColor;
        if (leapProvider == null)
        {
            leapProvider = FindObjectOfType<LeapServiceProvider>();
            if (leapProvider == null)
            {
                Debug.LogError("LeapServiceProvider not found. Please assign it in the inspector.");
            }
        }

        audioButton.onClick.AddListener(PressAudioButton);
        accelButton.onClick.AddListener(PressAccelButton);
        comboButton.onClick.AddListener(PressComboButton);

        SetSelectedButton(audioButton);
    }

 
    //Functionality for camera handling when pressing keyboard button 1, 2, 3 or 4
    void Update()
    {
        if(Input.GetKeyDown(KeyCode.Alpha1)){//Big comb visualization
            mainCamera.transform.position = new Vector3 (-3.908f, -3.702f, -5.725f);
            mainCamera.transform.rotation = Quaternion.Euler(42.02f, -41.137f, 0f);
            leapProviderOffset = new Vector3(0f, -0.015f, 0.048f);
        }
        else if(Input.GetKeyDown(KeyCode.Alpha2)){//Sandpaper visualization
            mainCamera.transform.position = new Vector3 (-3.856f, -3.702f, -5.638f);
            mainCamera.transform.rotation = Quaternion.Euler(48.699f, 12.751f, 0.821f);
        }else if(Input.GetKeyDown(KeyCode.Alpha3)){//Small comb visualization
            mainCamera.transform.position = new Vector3(-3.7452f, -3.6853f, -5.7399f);
            mainCamera.transform.rotation = Quaternion.Euler(46.347f, 52.565f, 1.51f);
        }
        else if(Input.GetKeyDown(KeyCode.Alpha4)){ //Desk visualization
            mainCamera.transform.position = new Vector3 (-3.78f, -3.65f, -6.21f);
            mainCamera.transform.rotation = Quaternion.Euler(29.935f, -0.215f, -4.826f);
        }
        else if (Input.GetKeyDown(KeyCode.S))
        { //first interaction
            mainCamera.transform.position = new Vector3(-3.6091f, -3.8182f, -6.2349f);
            mainCamera.transform.rotation = Quaternion.Euler(25.7089f, 88.701f, 0f);
        }
        else if (Input.GetKeyDown(KeyCode.A))
        { //first interaction
            mainCamera.transform.position = new Vector3(-3.6091f, -3.8182f, -6.013f);
            mainCamera.transform.rotation = Quaternion.Euler(25.7089f, 88.701f, 0f);
        }
        else if (Input.GetKeyDown(KeyCode.D))
        { //first interaction
            mainCamera.transform.position = new Vector3(-3.6091f, -3.8182f, -6.485f);
            mainCamera.transform.rotation = Quaternion.Euler(25.7089f, 88.701f, 0f);
        }
        if (leapProvider != null)
        {
            Vector3 offset = new Vector3(0f, -0.025f, 0.04f); // Offset: 0.02 on Y, 0.03 on Z
            leapProvider.transform.position = mainCamera.transform.position + mainCamera.transform.TransformVector(leapProviderOffset);
        }

    }


    //Audio Button Functionality
    public void PressAudioButton()
    {
        SetSelectedButton(audioButton);
        if(audioDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 0)
        {
            big_comb.tag = "1";
            small_comb.tag = "2";
            sandpaper.tag = "3";
            
        }else if (audioDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 1)
        {
            big_comb.tag = "13";
            small_comb.tag = "14";
            sandpaper.tag = "15"; 
        }
    }

    //Acceleration Button Functionality
    public void PressAccelButton()
    {
        SetSelectedButton(accelButton);
        if (accelDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 0)
        {
            big_comb.tag = "4";
            small_comb.tag = "5";
            sandpaper.tag = "6";
            
        }
        else if (accelDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 1)
        {
            big_comb.tag = "10";
            small_comb.tag = "11";
            sandpaper.tag = "12";
            
        }
    }


    //Combination Button Functionality
    public void PressComboButton()
    {
        SetSelectedButton(comboButton);
        if (comboDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 0)
        {
            big_comb.tag = "7";
            small_comb.tag = "8";
            sandpaper.tag = "9";
            
        }
        else if (comboDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 1)
        {
            big_comb.tag = "16";
            small_comb.tag = "17";
            sandpaper.tag = "18";
            
        }

    }

    void SetSelectedButton(Button newButton)
    {
        if (currentButton != null)
        {
            var colors = currentButton.colors;
            colors.normalColor = Color.white;
            currentButton.colors = colors;
        }

        currentButton = newButton;
        var newColors = currentButton.colors;
        newColors.normalColor = Color.green;
        currentButton.colors = newColors;
        EventSystem.current.SetSelectedGameObject(currentButton.gameObject);
    }

    //Audio Dropdown Button Functionality
    public void AudioDropDown() {
        if (audioDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 0 && currentButton == audioButton)
        {
            big_comb.tag = "1";
            small_comb.tag = "2";
            sandpaper.tag = "3";
            
        }
        else if (audioDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 1 && currentButton == audioButton)
        {
            big_comb.tag = "13";
            small_comb.tag = "14";
            sandpaper.tag = "15";
            
        }
    }

    //Accelerometer Dropdown Button Functionality
    public void AccelDropDown()
    {
        if (accelDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 0 && currentButton==accelButton)
        {
            big_comb.tag = "4";
            small_comb.tag = "5";
            sandpaper.tag = "6";
            
        }
        else if (accelDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 1 && currentButton == accelButton)
        {
            big_comb.tag = "10";
            small_comb.tag = "11";
            sandpaper.tag = "12";
            
        }
    }

    //Combination Dropdown Button Functionality
    public void ComboDropDown()
    {
        if (comboDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 0 && currentButton == comboButton)
        {
            big_comb.tag = "7";
            small_comb.tag = "8";
            sandpaper.tag = "9";
           
        }
        else if (comboDropDown.GetComponent<TMPro.TMP_Dropdown>().value == 1 && currentButton == comboButton)
        {
            big_comb.tag = "16";
            small_comb.tag = "17";
            sandpaper.tag = "18";
            
        }
    }

    //Velocity Feature Toggle Button functionality
    public void VelocityFeature()
    {
        if (velocityFeatureButton.isOn) { 
            velocityFeatureOn = true; 
            Debug.Log("Boolean: "+velocityFeatureOn);
        }
        else if (!velocityFeatureButton.isOn) {
            velocityFeatureOn = false;
            Debug.Log("Boolean: " + velocityFeatureOn);
        }
    }

    public bool GetToggleState()
    {
        return velocityFeatureOn;
    }
}

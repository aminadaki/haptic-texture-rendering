using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class SetSelectedGameObject : MonoBehaviour
{
    public GameObject currentButton;
    EventSystem eventSystem;
    public GameObject buttonObj;

    void Start()
    {
        eventSystem = GameObject.Find("EventSystem").GetComponent<EventSystem>();
        //GameObject buttonObj = GameObject.Find("Button");
        buttonObj.GetComponent<Button>().onClick.AddListener(() => { currentButton = buttonObj; });
        //Debug.Log("current " + currentButton.name);
        //Debug.Log("buttonObj " + buttonObj.name);
    }
    
    void Update()
    {
        if (Input.GetMouseButtonDown(0)){
            eventSystem.SetSelectedGameObject(currentButton);
        }
    }
}

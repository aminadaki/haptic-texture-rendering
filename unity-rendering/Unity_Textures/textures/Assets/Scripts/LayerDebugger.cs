using System.Collections;
using System.Collections.Generic;
using UnityEngine;


public class LayerDebugger : MonoBehaviour
{
    private int previousLayer;

    void Start()
    {
        previousLayer = gameObject.layer;
    }

    void Update()
    {
        if (gameObject.layer != previousLayer)
        {
            Debug.Log("Layer changed from " + LayerMask.LayerToName(previousLayer) + " to " + LayerMask.LayerToName(gameObject.layer));
            previousLayer = gameObject.layer;
        }
    }
}

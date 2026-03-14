using UnityEngine;
using Leap.Unity.Interaction;
using System;
using Leap;

public class InteractionObjectSetup : MonoBehaviour
{
    private InteractionBehaviour interactionBehaviour;

    private void Start()
    {
        interactionBehaviour = GetComponent<InteractionBehaviour>();
        if (interactionBehaviour == null)
        {
            Debug.LogError("InteractionBehaviour component is missing on the cube.");
            return;
        }

        
        interactionBehaviour.OnContactBegin += OnContactBegin;
        interactionBehaviour.OnContactEnd += OnContactEnd;
    }

    private void OnContactBegin()
    {
        //check if the collider belongs to the bottom part of the index finger
        if (interactionBehaviour.contactingControllers.Count > 0)
        {
            foreach (var controller in interactionBehaviour.contactingControllers)
            {
                if (controller.intHand != null && IsIndexFingerBottom(controller.intHand))
                {
                    Debug.Log("Index finger bottom part collided with the cube!");
                    OnIndexFingerCollision();
                }
            }
        }
    }

    private bool IsIndexFingerBottom(InteractionHand intHand)
    {
        throw new NotImplementedException();
    }

    private void OnContactEnd()
    {

        Debug.Log("Contact ended");
    }

    private bool IsIndexFingerBottom(Hand hand)
    {
       
        var indexFinger = hand.Fingers[(int)Finger.FingerType.TYPE_INDEX];
        return indexFinger.Bone(Bone.BoneType.TYPE_DISTAL) != null;
    }

    private void OnIndexFingerCollision()
    {
        Debug.Log("Index finger bottom part collided with the cube.");
    }

    private void OnDestroy()
    {
        if (interactionBehaviour != null)
        {
            interactionBehaviour.OnContactBegin -= OnContactBegin;
            interactionBehaviour.OnContactEnd -= OnContactEnd;
        }
    }
}
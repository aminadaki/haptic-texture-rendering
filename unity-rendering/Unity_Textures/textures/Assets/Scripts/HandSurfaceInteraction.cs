using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HandSurfaceInteraction : MonoBehaviour
{
    private Rigidbody fingertipRigidbody; //reference to the hand or fingertip's Rigidbody
    private Collider fingertipCollider;
    public float surfaceHeight = 0.0f; //Y position of the surface
    public float lockThreshold = 0.01f;
    public float releaseThreshold = 0.05f; 

    private bool isGrounded = false; 
    private bool isSliding = false; 

    void Start()
    {
        fingertipRigidbody = GetComponent<Rigidbody>();
        fingertipCollider = GetComponent<Collider>();
        if (fingertipRigidbody == null)
        {
            Debug.LogError("Rigidbody not assigned to fingertip.");
        }
    }

    void Update()
    {
        Vector3 fingertipPosition = fingertipRigidbody.transform.position;
        Vector3 fingertipColPosition = fingertipCollider.transform.position;

        float distanceToSurface = Mathf.Abs(fingertipPosition.y - surfaceHeight);
        float distanceToSurfaceCol = Mathf.Abs(fingertipColPosition.y - surfaceHeight);

        if (distanceToSurface < lockThreshold && !isSliding)
        {
            isGrounded = true;
            isSliding = true;
            Debug.Log("Hand is grounded. Y-axis locked to surface.");
        }
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
            Debug.Log("Hand lifted. Y-axis unlocked.");
        }
    }

    bool ValidTag(string tag)
    {
        return tag == "4_megalo" || tag == "4_mikro" || tag == "4_sandpaper" || tag == "5_megalo" || tag == "5_mikro" || tag == "5_sandpaper" ||
               tag == "7_megalo" || tag == "7_mikro" || tag == "7_sandpaper" || tag == "8_megalo" || tag == "8_mikro" || tag == "8_sandpaper" ||
               tag == "14_megalo" || tag == "14_mikro" || tag == "14_sandpaper" || tag == "15_megalo" || tag == "15_mikro" || tag == "15_sandpaper" ||
               tag == "16_megalo" || tag == "16_mikro" || tag == "16_sandpaper" || tag == "20_megalo" || tag == "20_mikro" || tag == "20_sandpaper" ||
               tag == "26_megalo" || tag == "26_mikro" || tag == "26_sandpaper" || tag == "27_megalo" || tag == "27_mikro" || tag == "27_sandpaper";
    }

    void OnCollisionEnter(Collision collision)
    {
        if (ValidTag(collision.gameObject.tag))
        {
            surfaceHeight = collision.contacts[0].point.y; 
            isGrounded = true;
            Debug.Log($"Collision Enter detected with {collision.gameObject.tag}. Surface height set to {surfaceHeight}");
        }
    }

    void OnCollisionExit(Collision collision)
    {
        if (ValidTag(collision.gameObject.tag))
        {
            isGrounded = false;
            isSliding = false;
            Debug.Log("Collision exit detected.");
        }
    }
}
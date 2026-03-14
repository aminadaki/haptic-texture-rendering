using System.Collections;
using UnityEngine;
using Leap.Unity.Interaction;

public class FingertipManager : MonoBehaviour
{
    public InteractionManager interactionManager;
    public Camera_Movement cameraMovement;
    private bool setupCompleted = false;

    void Start()
    {
        StartCoroutine(CheckAndSetupFingertipScripts());
    }

    IEnumerator CheckAndSetupFingertipScripts()
    {
        while (!setupCompleted)
        {
            if (interactionManager == null)
            {
                Debug.LogError("InteractionManager reference is not set in FingertipManager.");
                yield break;
            }

            foreach (var controller in interactionManager.interactionControllers)
            {
                if (controller is InteractionHand rightHand && rightHand.isTracked && rightHand.leapHand.IsRight)
                {
                    Debug.Log("Right hand found.");

                    GameObject rightHandContactBones = GameObject.Find("Right Interaction Hand Contact Bones");
                    if (rightHandContactBones == null)
                    {
                        Debug.LogWarning("Right Interaction Hand Contact Bones GameObject not found yet.");
                        yield return new WaitForSeconds(0.5f);
                        continue;
                    }

                    if (rightHandContactBones.transform.childCount < 6)
                    {
                        Debug.LogWarning("Right Interaction Hand Contact Bones does not have enough children yet.");
                        yield return new WaitForSeconds(0.5f);
                        continue;
                    }

                    Transform indexFingertip = rightHandContactBones.transform.GetChild(5);

                    if (indexFingertip != null)
                    {
                        Debug.Log("Index fingertip found: " + indexFingertip.name);

                        if (indexFingertip.gameObject.GetComponent<FingertipColliderManager>() == null)
                        {
                            
                            FingertipColliderManager manager = indexFingertip.gameObject.AddComponent<FingertipColliderManager>(); //add the FingertipColliderManager dynamically
                            //pass the Camera_Movement reference to the FingertipColliderManager
                            if (cameraMovement != null)
                            {
                                manager.Initialize(cameraMovement);
                                Debug.Log("Camera_Movement reference passed to FingertipColliderManager.");
                            }
                            else
                            {
                                Debug.LogError("Camera_Movement reference is not assigned in FingertipManager.");
                            }
                        }

                        setupCompleted = true;
                        yield break;
                    }
                    else
                    {
                        Debug.LogError("Index fingertip contact bone not found.");
                    }
                }
            }

            if (!setupCompleted)
            {
                Debug.LogWarning("Right interaction hand not found yet.");
            }

            yield return new WaitForSeconds(0.5f);
        }
    }
}
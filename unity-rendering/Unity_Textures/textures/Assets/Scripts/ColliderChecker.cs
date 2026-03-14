using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ColliderChecker : MonoBehaviour
{
    private HashSet<GameObject> checkedObjects = new HashSet<GameObject>();  //list to keep track of checked objects

    void Start()
    {
        CheckAllObjects();
    }

    void Update()
    {
        CheckAllObjects();
    }

    void CheckAllObjects()
    {
        GameObject[] allObjects = FindObjectsOfType<GameObject>();
        foreach (GameObject obj in allObjects)
        {
            if (!checkedObjects.Contains(obj))
            {
                CheckAndCorrectColliders(obj);
                checkedObjects.Add(obj);
            }
        }
    }

    void CheckAndCorrectColliders(GameObject obj)
    {
        Collider[] colliders = obj.GetComponentsInChildren<Collider>(true);
        foreach (Collider collider in colliders)
        {
            if (!(collider is BoxCollider || collider is SphereCollider || collider is CapsuleCollider || (collider is MeshCollider meshCollider && meshCollider.convex)))
            {
                Debug.Log($"Unsupported collider type detected on {obj.name} (Collider type: {collider.GetType()}). Please use BoxCollider, SphereCollider, CapsuleCollider, or convex MeshCollider.");

            }
        }
    }
}
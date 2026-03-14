using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TagAssigner : MonoBehaviour
{
    void Start()
    {
        for (int i = 0; i < 32; i++)
        {
            string cubeName = i == 0 ? "Cube" : $"Cube ({i})";
            GameObject cube = GameObject.Find(cubeName);

            if (cube != null)
            {
                cube.tag = (i + 1).ToString();
                Debug.Log($"Assigned tag {(i + 1)} to {cubeName}");
            }
            else
            {
                Debug.LogWarning($"GameObject '{cubeName}' not found in the scene.");
            }
        }
    }
}

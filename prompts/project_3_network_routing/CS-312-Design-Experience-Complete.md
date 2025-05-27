# CS 312 Design Experience Template

**Project Title:**  
_(Project 3: Network Routing)_

**Your Name:**  
_(Wiley Welch)_

**Partner’s Name (if applicable):**  
_(Rubber-Duck)_

**Date of Design Experience:**  
_(05/23/2025)_

---


# Algorithm Design Worksheet

Use this worksheet to guide your thinking as you design and analyze your algorithm. Be thorough in each section and support your reasoning with clear logic and evidence.

---

## 1. Problem Understanding

- **What is the problem?**  
  _Write a clear description of the problem you're solving._

```
We are tasked with finding the shortest path between two nodes in a network. The network is represented as a weighted directed graph, where each node represents a router and each edge represents a connection with a transmission cost.
```

- **How does your algorithm solve this problem?**  
  _Summarize the approach or strategy behind your solution._

```
We will implement Dijkstra’s algorithm using a priority queue (min-heap) to efficiently find the shortest path from a source node to a target node. The algorithm will maintain a distance map to track the shortest known distance to each node and a predecessor map to reconstruct the path once the target is reached.
```

---

## 2. Algorithmic Steps

- **Describe the step-by-step process of your algorithm:**  
  _Use clear and ordered steps from start to finish._
```
Dijkstra’s Algorithm using a Min-Heap
1. Initialize a distance map with all nodes set to infinity except the source node (set to 0).
2. Initialize a priority queue (min-heap) and insert the source node with priority 0.
3. While the priority queue is not empty:
   a. Extract the node with the minimum distance.
   b. For each neighbor of the current node:
      i. Calculate the new potential distance via the current node.
      ii. If the new distance is less than the recorded distance:
          - Update the distance map.
          - Update the priority queue with the new priority.
4. Reconstruct the path from source to target using a predecessor map.
5. Return the shortest path and its total cost.
```
**If you are using multiple versions (variants) of the algorithm:**  
_Describe the alternate steps between them. Use numbered steps._
```
  1. Variant A: Using Array-Based Priority Queue
    - Same as above, but instead of a binary heap, use an unsorted array.
    - Finding the node with the minimum distance now takes O(|V|) time instead of O(log|V|).
  
  2. Variant B: Using Binary Heap Priority Queue
    - Uses a custom binary heap where all operations (insert, delete-min, decrease-key) are O(log|V|).
    - Maintains a position map to allow fast decrease-key operation.
```
---

## 3. Data Structures

- **Which data structures are you using?**  
  _List them and explain why they’re appropriate._

- **What are the pros and cons of your data structure choices?**
```  
  - Min-Heap (Binary Heap):
    - Pros: Efficient insert and extract-min operations (O(log n)).
    - Cons: Requires additional map to support efficient decrease-key.

  - Array/List:
    - Pros: Simple and fast to implement.
    - Cons: Inefficient extract-min (O(n)) makes it slow for large graphs.
```

**Write key sub-methods or helper functions in pseudocode (Python-style):**

---
```python
# Array Class Submethods

def decrease_key(self, item, new_key):
    if item in self.queue:
        if new_key < self.queue[item]:
            self.queue[item] = new_key
    else:
        raise KeyError("Item does not exist in the queue")

def delete_min(self):
    if self.queue_empty():
        raise IndexError("Queue is empty")
    min_item = min(self.queue, key=self.queue.get)
    del self.queue[min_item]
    return min_item

# Heap Class Submethods
def heapify_up(self, index):
    while index > 0 and self.heap[self.find_parent(index)][0] > self.heap[index][0]:
        parent_index = self.find_parent(index)
        # Swap elements in the heap
        self.heap[index], self.heap[parent_index] = self.heap[parent_index], self.heap[index]
        # Update the position map
        self.position_map[self.heap[index][1]] = index
        self.position_map[self.heap[parent_index][1]] = parent_index
        index = parent_index

def heapify_down(self, index):
    smallest = index
    left = self.left_child(index)
    right = self.right_child(index)

    if left < len(self.heap) and self.heap[left][0] < self.heap[smallest][0]:
        smallest = left
    if right < len(self.heap) and self.heap[right][0] < self.heap[smallest][0]:
        smallest = right
    if smallest != index:
        # Swap elements in the heap
        self.heap[index], self.heap[smallest] = self.heap[smallest], self.heap[index]
        # Update the position map
        self.position_map[self.heap[index][1]] = index
        self.position_map[self.heap[smallest][1]] = smallest
        self.heapify_down(smallest)

def insert(self, item):
    self.heap.append(item)
    index = len(self.heap) - 1
    self.position_map[item[1]] = index  # Ensure this line is present
    self.heapify_up(index)

def decrease_key(self, item, new_val):
    # If the item isn't in the heap, insert it with the new value
    if item not in self.position_map:
        self.insert((new_val, item))
    else:
        # If the item is in the heap, decrease its key
        index = self.position_map[item]

        # Additional check: Ensure the index is valid for the current heap size
        if index >= len(self.heap):
            raise IndexError(f"Invalid index {index} for item {item} in heap")
        self.heap[index] = (new_val, item)  # Update the heap with the new value
        self.heapify_up(index)

def delete_min(self):
    if len(self.heap) == 0:
        return None
    if len(self.heap) == 1:
        node = self.heap.pop()
        del self.position_map[node[1]]
        return node
    root = self.heap[0]
    self.heap[0] = self.heap.pop()  # Swap with last element
    if self.heap:
        self.position_map[self.heap[0][1]] = 0
    del self.position_map[root[1]]
    self.heapify_down(0)  # Fix heap property
    return root

```

---

## 4. Time & Space Complexity

- **What is the overall time complexity of your algorithm?**  
  _Use Big-O notation (e.g., O(n log n), O(n²))._
  
```
  - Heap-based Dijkstra:
    Time: O((V + E) log V)
    Space: O(V)
  - Array-based Dijkstra:
    Time: O(V^2 + E)
    Space: O(V)
```

- **What is the overall space complexity?**
```
  - O(n) for both heap and array implementations, where n is the number of nodes in the graph.
```

- **What are the main contributors to the time and space cost?**  
  _Explain which parts of the algorithm have the biggest impact._
```
  - Time complexity is dominated by the priority queue operations (insert and extract-min) for the heap-based version. For the array version, it is the delete operation that takes the longest.
  - Space complexity is due to the queue size or the amount of nodes in the graph.
```


---

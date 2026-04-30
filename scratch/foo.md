# Complexity Analysis Report

## Introduction

This report presents a detailed complexity analysis of the provided Python code, which implements Fermat's primality test and the Miller-Rabin primality test. These tests are probabilistic algorithms used to determine whether a given number \( N \) is prime. The number of iterations \( k \) affects the accuracy and computational complexity of the tests. The key functions analyzed are:

- `mod_exp(x, y, N)`: Computes \( x^y \mod N \) efficiently.
- `fermat(N, k)`: Implements Fermat's primality test.
- `miller_rabin(N, k)`: Implements the Miller-Rabin primality test.

## Assumptions

For this complexity analysis, we make the following assumptions:

1. **Bit Length (\( n \))**: Let \( n \) be the number of bits required to represent the integer \( N \). That is, \( n = \lceil \log_2 N \rceil \).

2. **Arithmetic Operations**:

   - **Addition/Subtraction**: Operations on \( n \)-bit integers take \( O(n) \) time.
   - **Multiplication**: Multiplying two \( n \)-bit integers takes \( O(n^2) \) time using the standard algorithm.
   - **Modulo Operation**: Calculated via division; thus, modulo operations on \( n \)-bit integers also take \( O(n^2) \) time.
   - **Bitwise Operations**: Bit shifts (\( << \), \( >> \)), bitwise AND (\( & \)), and comparisons are considered to take \( O(n) \) time on \( n \)-bit integers.

3. **Random Number Generation**:

   - Generating a random integer in the range \([1, N-1]\) takes \( O(n) \) time.

4. **Function Calls**:

   - The overhead from function calls is negligible compared to the time taken by arithmetic operations on large integers.

5. **Modern Computer Architecture**:

   - We assume operations are performed on a standard modern computer without specialized hardware for big integer arithmetic.

## Complexity Analysis

### 1. `mod_exp(x, y, N)`

#### Function Overview

The `mod_exp` function computes \( x^y \mod N \) using recursive exponentiation by squaring:

```python
def mod_exp(x: int, y: int, N: int) -> int:
    if y == 0:
        return 1
    z = mod_exp(x, y // 2, N)
    if y % 2 == 0:
        return (z * z) % N
    else:
        return (x * z * z) % N
```

#### Time Complexity Analysis

- **Recursive Calls**: The function recursively calls itself with \( y \) halved each time. This results in \( O(\log y) \) recursive calls.
- **Operations per Call**:

  - **Multiplications**:
    - Each call performs up to two multiplications involving \( n \)-bit numbers.
    - Time per multiplication: \( O(n^2) \).
  - **Modulo Operation**:
    - Each modulo operation involves \( n \)-bit numbers.
    - Time per modulo: \( O(n^2) \).

- **Total Time per Call**: \( O(n^2) \) (since the multiplications and modulo dominate).

- **Total Time Complexity**:

  - Since there are \( O(\log y) \) recursive calls and each takes \( O(n^2) \) time:
  - \( O(n^2 \cdot \log y) \).

- **Worst-Case Scenario**:

  - The exponent \( y \) can be as large as \( N \), so \( \log y = O(n) \).
  - Thus, the total time complexity is \( O(n^2 \cdot n) = O(n^3) \).

**Conclusion**: The `mod_exp` function has a time complexity of \( O(n^3) \).

### 2. `fermat(N, k)`

#### Function Overview

The `fermat` function implements Fermat's primality test, performing \( k \) iterations:

```python
def fermat(N: int, k: int) -> str:
    for _ in range(k):
        a = random.randint(1, N - 1)
        if mod_exp(a, N - 1, N) != 1:
            return "composite"
    return "prime"
```

#### Time Complexity Analysis

- **Iterations**: Up to \( k \) iterations (tests).
- **Per Iteration**:

  - **Random Number Generation**:
    - Time: \( O(n) \) to generate an \( n \)-bit random integer.
  - **Modular Exponentiation**:
    - Calls `mod_exp(a, N - 1, N)`.
    - Time: \( O(n^3) \) per our previous analysis.

- **Total Time Complexity**:

  - \( O(k \cdot (n + n^3)) = O(k \cdot n^3) \).

**Conclusion**: The `fermat` function has a time complexity of \( O(k \cdot n^3) \).

### 3. `miller_rabin(N, k)`

#### Function Overview

The `miller_rabin` function implements the Miller-Rabin primality test, performing \( k \) iterations:

```python
def miller_rabin(N: int, k: int) -> str:
    def single_test(N: int, a: int) -> bool:
        d = N - 1
        while not d & 1:
            d >>= 1
        if mod_exp(a, d, N) == 1:
            return True
        while d < N - 1:
            if mod_exp(a, d, N) == N - 1:
                return True
            d <<= 1
        return False
    for _ in range(k):
        a = random.randint(2, N - 1)
        if not single_test(N, a):
            return "composite"
    return "prime"
```

#### Time Complexity Analysis

##### **Single Test (`single_test`)**

- **Initialization**:

  - **Compute \( d \) such that \( N - 1 = 2^s \cdot d \) with \( d \) odd**:
    - Repeatedly divide \( d \) by 2 until it is odd.
    - Number of divisions: \( s \), where \( s \leq n \) (since \( N - 1 < 2^n \)).
    - Time per division: \( O(n) \) (bit shift and check).
    - Total time: \( O(s \cdot n) = O(n^2) \).

- **First Modulo Exponentiation Check**:

  - **Compute \( x = a^d \mod N \)**:
    - Time: \( O(n^3) \) (from `mod_exp`).

- **Witness Loop**:

  - **Iterations**: Up to \( s \) times (since \( d \) doubles each time until \( d = N - 1 \)).
  - **Operations per Iteration**:

    - **Modulo Exponentiation**:
      - Compute \( a^d \mod N \).
      - Time: \( O(n^3) \) per iteration.
    - **Update \( d \)**:
      - Multiply \( d \) by 2 (left shift).
      - Time: \( O(n) \).

  - **Total Time**:

    - Time per iteration: \( O(n^3 + n) = O(n^3) \).
    - Total for all iterations: \( O(s \cdot n^3) = O(n \cdot n^3) = O(n^4) \).

- **Total Time Complexity of `single_test`**:

  - \( O(n^2) \) (initialization) \( + \) \( O(n^3) \) (first check) \( + \) \( O(n^4) \) (witness loop) \( = O(n^4) \).

##### **Overall `miller_rabin` Function**

- **Iterations**: Up to \( k \) iterations.
- **Per Iteration**:

  - **Random Number Generation**:
    - Time: \( O(n) \).
  - **Single Test**:
    - Time: \( O(n^4) \).

- **Total Time Complexity**:

  - \( O(k \cdot (n + n^4)) = O(k \cdot n^4) \).

**Conclusion**: The `miller_rabin` function has a time complexity of \( O(k \cdot n^4) \).

## Summary

- **`mod_exp`**:
  - Time Complexity: \( O(n^3) \).
  - Purpose: Efficient computation of \( x^y \mod N \).

- **`fermat`**:
  - Time Complexity: \( O(k \cdot n^3) \).
  - Purpose: Performs \( k \) iterations of Fermat's primality test.

- **`miller_rabin`**:
  - Time Complexity: \( O(k \cdot n^4) \).
  - Purpose: Performs \( k \) iterations of the Miller-Rabin primality test.

The additional computational overhead in the `miller_rabin` function compared to `fermat` is due to the more complex structure of the Miller-Rabin test, which involves multiple modular exponentiations within each single test iteration.

## Conclusion

The analysis shows that:

- The `mod_exp` function is critical for both primality tests and has a cubic time complexity with respect to the bit length of \( N \).
- The Fermat test is less computationally intensive per iteration than the Miller-Rabin test but provides weaker probabilistic guarantees.
- The Miller-Rabin test, while more computationally intensive (\( O(n^4) \) per iteration), offers stronger probabilistic assurances of primality.

For large values of \( N \) and \( k \), the computational cost becomes significant, and optimizations or alternative algorithms may be considered to improve performance.

---

**Note**: This analysis provides an upper bound on the time complexities and assumes standard algorithms for arithmetic operations. Advanced algorithms (e.g., Karatsuba multiplication) can reduce the time complexities of multiplication and exponentiation, affecting the overall time complexities of the functions.

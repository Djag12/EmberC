int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
int add(int a, int b) {
    return a + b;
}
int main(void) {
    return add(factorial(5), 7);
}

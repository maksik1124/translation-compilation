#include <iostream>
using namespace std;
int multiply(int x, int y) {
return x * y;
}
int main() {
int a = 5;
int b = 3;
int sum = 0;
int diff = 0;
int product = 0;
bool flag = false;
sum = a + b;
diff = a - b;
product = multiply(a, b);
flag = (sum > diff) && (product != 0);
if (flag) {
cout << "Flag is true" << endl;
} else {
cout << "Flag is false" << endl;
}
for (int i = 0; i < 3; i++) {
cout << i << " ";
}
cout << endl;
int counter = 0;
while (counter < 2) {
cout << counter << endl;
counter++;
}
return 0;
}
#include <iostream>
using namespace std;

/* 
   Функция умножения двух чисел
*/
int multiply(int x, int y) {
    return x * y;      // Возвращаем произведение
}

int main() {
    // Объявление переменных
    int a = 5;
    int b = 3;    
    int sum = 0;
    int diff = 0;
    int product = 0;
    bool flag = false;

    /* Арифметические операции */
    sum = a + b;
    diff = a - b;
    product = multiply(a, b);

    // Логическое выражение
    flag = (sum > diff) && (product != 0);

    // Условный оператор
    if (flag) {
        cout << "Flag is true" << endl;
    } else {
        cout << "Flag is false" << endl;
    }

    // Цикл for
    for (int i = 0; i < 3; i++) {
        cout << i << " ";
    }

    cout << endl;

    // Цикл while
    int counter = 0;
    while (counter < 2) {
        cout << counter << endl;
        counter++;
    }

    return 0;
}
#include <iostream>
#include <random>
#include <thread>
#include <chrono>

int main() {
    // Generador de números aleatorios basado en Mersenne Twister
    std::random_device rd;  // Dispositivo de entropía para semilla
    std::mt19937 gen(rd()); // Generador inicializado con la semilla

    // Distribuciones uniformes para cada variable
    std::uniform_int_distribution<> temp_dist(20, 29);   // Temperatura: 20–29 °C
    std::uniform_int_distribution<> hum_dist(40, 59);    // Humedad: 40–59 %
    std::uniform_int_distribution<> co2_dist(300, 699);  // CO₂: 300–699 ppm

    while (true) {
        int temp = temp_dist(gen);
        int hum  = hum_dist(gen);
        int co2  = co2_dist(gen);

        // Imprime datos formateados
        std::cout << "T:" << temp 
                  << ",H:" << hum 
                  << ",CO2:" << co2 
                  << std::endl;

        // Espera 1 segundo
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    return 0;
}

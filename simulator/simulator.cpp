#include <iostream>
#include <random>
#include <thread>
#include <chrono>

int main() {
    // Mersenne Twister-based random number generator
    std::random_device rd;  // Entropy device for seeding
    std::mt19937 gen(rd()); // Generator initialized with the seed

    // Uniform distributions for each variable
    std::uniform_int_distribution<> temp_dist(-25, 55);   // Temperature: -25 to 55 °C
    std::uniform_int_distribution<> hum_dist(0, 100);    // Humidity: 0 to 100%
    std::uniform_int_distribution<> co2_dist(300, 2000);  // CO₂: 300 to 2000 ppm

    while (true) {
        int temp = temp_dist(gen);
        int hum  = hum_dist(gen);
        int co2  = co2_dist(gen);

        // Print formatted data
        std::cout << "T:" << temp 
                  << ",H:" << hum 
                  << ",CO2:" << co2 
                  << std::endl;

        // Wait for 1 second
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }

    return 0;
}

# Scan Accelerator Utils (SCAUT) 

Software package for the orchestration of accelerator experiments.

## Thesis

Scaut is a modern library for orchestrating accelerator experiments. Modern accelerator experiments require high levels of automation and reliable coordination between the equipment and the control and diagnostic software systems. The scaut library was developed to meet these requirements, providing flexibility, reliability, and scalability. Unlike existing solutions, scaut is tailored to the specifics of accelerator facilities, allowing it to integrate control, diagnostics, and modeling systems, significantly enhancing the efficiency of experimental time usage on installations.

One of the key features of the library is the ability to model beam dynamics in various programs, enabling researchers to conduct virtual experiments on a computer before actual trials. This allows for the advance assessment of beam behavior under different conditions and scenarios, greatly reducing the time needed for setup and optimization in real conditions. Modeling helps identify potential issues and optimize experimental parameters before they are implemented on the equipment.

The main capabilities of the library include real-time data transmission, metadata collection, flexibility in managing experimental scenarios, and recovery options after failures. These features allow researchers not only to optimize processes but also to minimize downtime, which is especially important under high demands for experimental time.

Currently, scaut is successfully used at the SKIF injector linear accelerator, where its effectiveness has been demonstrated in real experimental conditions. For example, automating key stages of operation leads to a significant reduction in the time required for accelerator optics setup, making the process more reliable and predictable. The library provides a high level of integration with the scientific Python stack, making it easy to adapt to specific tasks and expand its functionality.

In the future, there are plans to develop scaut through the integration of machine learning methods to optimize equipment management and increase automation levels. Open-source code and documentation foster the creation of an active community ready to contribute improvements and extensions, making the library a promising tool for the scientific community in the field of accelerator physics.

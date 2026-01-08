# Chemistry 169 - Lab 1: Beer-Lambert Law

Welcome to Lab 1! In this lab, you will explore the Beer-Lambert Law and use it to determine the concentration of an unknown solution.

## Learning Objectives

- Understand the relationship between absorbance and concentration
- Create calibration curves using spectrophotometry data
- Apply linear regression to experimental data

---

## Exercise 1: Data Loading

Load the provided CSV file `absorbance_data.csv` containing wavelength and absorbance measurements for five standard solutions with known concentrations.

Display the first few rows of the data to verify it loaded correctly.

## Exercise 2: Beer-Lambert Equation

Write a markdown cell explaining the Beer-Lambert Law equation:

A = εlc

Where:
- A is absorbance (unitless)
- ε is the molar absorptivity (L/mol·cm)
- l is the path length (cm)
- c is the concentration (mol/L)

Explain why this relationship allows us to create a calibration curve.

## Exercise 3: Calibration Curve

Create a scatter plot of absorbance (y-axis) vs. concentration (x-axis) for the standard solutions.

Requirements:
- Add appropriate axis labels with units
- Add a title to the plot
- Use a clear marker style

## Exercise 4: Linear Regression

Fit a linear regression line to your calibration data. Report:
- The slope (which corresponds to ε × l)
- The R² value
- Add the regression line to your plot from Exercise 3

## Exercise 5: Unknown Concentration

The unknown solution has an absorbance of 0.425 at the measurement wavelength.

Using your calibration curve, calculate the concentration of the unknown solution. Show your work and report the final answer with appropriate significant figures.

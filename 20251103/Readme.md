# Contactless Finger SDK for Android

This document provides instructions on how to integrate and use the Contactless Finger SDK for Android to capture fingerprint images.

## Table of Contents

- [Overview](#overview)
- [Integration](#integration)
  - [Method 1: Direct Installation and Intent Call](#method-1-direct-installation-and-intent-call)
  - [Method 2: AAR Library Integration](#method-2-aar-library-integration)
- [Usage](#usage)
  - [Input: PidOptions](#input-pidoptions)
  - [Output: Fingerprint Data](#output-fingerprint-data)
- [Image Processing](#image-processing)
- [Code Explanation](#code-explanation)

---

## Overview

The Contactless Finger SDK allows your Android application to capture fingerprint images using the device's camera. The captured image is processed into a black and white format and stored securely in the app's private storage. The SDK then returns a URI to a text file containing the base64 encoded image data, which your app can then read and use for embedding or other purposes.

---

## Integration

There are two primary methods to integrate the Contactless Finger SDK into your application.

### Method 1: Direct Installation and Intent Call

This method is suitable when the SDK is installed on the device as a standalone application. Your application can then invoke the SDK's capture functionality by calling a specific intent.

1.  **Ensure the SDK is installed** on the target Android device.
2.  In your application, create an Intent to start the capture activity using the following filter details:

    ```xml
    <intent-filter>
        <action android:name="in.gov.uidai.contactlessfingersdk_sita.CAPTURE" />
        <category android:name="android.intent.category.DEFAULT" />
    </intent-filter>
    ```

3.  Pass the required `pidOptions` XML string as an extra in the Intent.
4.  Call `startActivityForResult()` with this intent to launch the capture screen.

### Method 2: AAR Library Integration

This method involves including the SDK as an AAR (Android Archive) library directly in your project.

1.  **Build and publish the AAR file** to your local Maven repository. Use the following Gradle commands from the SDK's root directory:
    *   For a debug build:
        ```shell
        gradlew publishDebugPublicationToMavenLocal
        ```
    *   For a release build:
        ```shell
        gradlew publishReleasePublicationToMavenLocal
        ```

2.  **Add the dependency** to your app's `build.gradle` file:

    ```groovy
    dependencies {
        implementation "in.gov.uidai.sdk:contactless-biometric:alpha-01"
    }
    ```

3.  **Use the `CaptureSDK` object** provided by the library to create the capture intent. This object simplifies the process of building the intent. Then, call `startActivityForResult()` to initiate the fingerprint capture process.

---

## Usage

### Input: PidOptions

The SDK requires a `pidOptions` XML string to be passed as an extra in the intent. **The application will crash unexpectedly if this input is not provided.**

The format of the `pidOptions` XML must be as follows:

```xml
"<PidOptions ver=\"1.0\" env=\"${env.tag}\">\n" +
"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" +
"<Opts envName=\"${env.name}\" fCount=\"\" fType=\"\" iCount=\"\" iType=\"\" pCount=\"\" pType=\"\" format=\"\" pidVer=\"2.0\" timeout=\"\" otp=\"\" wadh=\"${wadhKey}\" posh=\"\" />\n" +
"<CustOpts>\n" +
"<Param name=\"txnld\" value=\"${txnld}\"/>\n" +
"<Param name=\"purpose\" value=\"${purpose}\"/>\n" +
"<Param name=\"language\" value=\"${LANGUAGE}\"/>\n" +
"<Param name=\"cameraUsage\" value=\"F\"/>\n" +
"<Param name=\"auaCode\" value=\"${auaCode}\"/>\n" +
"<Param name=\"auaName\" value=\"${auaName}\"/>\n" +
"</CustOpts>\n" +
"</PidOptions>"
```

**Note:** You must replace the `${...}` placeholders with your actual configuration values.

### Output: Fingerprint Data

On a successful capture, the SDK returns the result to your calling activity's `onActivityResult()` method.

*   **Result Code:** `Activity.RESULT_OK` indicates that the capture was successful.
*   **Result Data:** The `data` parameter of `onActivityResult()` will be an Intent containing a URI.

This URI points to a text file located in the SDK's private storage. The file contains the final, processed fingerprint image encoded as a **base64 string**.

To retrieve and use the image, your application should:
1.  Extract the URI from the result data.
2.  Use a `ContentResolver` to open an `InputStream` for that URI.
3.  Read the contents of the file to get the base64 string.
4.  Decode the base64 string to get the image byte array.
5.  Convert the byte array into a `Bitmap` for display or further processing.

---

## Image Processing

The SDK captures a high-resolution image from the camera and performs several processing steps to isolate the fingerprint and convert it into a standardized black and white image, which is optimal for biometric analysis.

---

## Code Explanation

*[This section is a placeholder for a detailed explanation of the SDK's internal code, architecture, and key classes. You can add details about the capture logic, image processing pipeline, and how the data is securely handled and returned.]*
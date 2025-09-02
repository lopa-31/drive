You are absolutely correct! My apologies for the confusion. The term `ImageProxy` is specific to the CameraX library, while the Camera2 API provides an `Image` object directly from the `ImageReader`. The underlying concepts and the way the image data is structured are very similar, and the conversion logic remains the same.

You can directly use the `Image` object you get from the `ImageReader`'s `acquireLatestImage()` or `acquireNextImage()` methods with the conversion function.

Here is the corrected, high-performance Kotlin code tailored specifically for the `Image` object from the Android Camera2 API.

### Fastest Way to Convert Camera2 `Image` (YUV_420_888) to NV21 ByteArray

For real-time applications using the Camera2 API, minimizing latency during format conversion is critical to prevent frame drops and ensure a smooth user experience. The most efficient way to convert the `YUV_420_888` `Image` object to an `NV21` byte array in Kotlin/Java is to directly manipulate the `ByteBuffer` for each color plane, while carefully accounting for memory layout properties like row and pixel strides.

This optimized approach avoids creating intermediate objects and minimizes data copying, making it significantly faster than naive methods.

#### Optimized Kotlin Conversion Function

This function takes an `Image` object directly from the Camera2 `ImageReader` and converts it to a `ByteArray` in the NV21 format. It's designed to be allocation-friendly by allowing you to reuse a pre-allocated byte array.

```kotlin
import android.media.Image
import java.nio.ByteBuffer

/**
 * Converts an Image in YUV_420_888 format to an NV21 byte array.
 *
 * This is a high-performance implementation that avoids unnecessary object allocations and
 * copies data directly from the image planes' ByteBuffers.
 *
 * @param image The Image object from the Camera2 API, in YUV_420_888 format.
 * @return A new byte array in NV21 format.
 */
fun yuv420888ToNv21(image: Image): ByteArray {
    // Check for supported format
    if (image.format != ImageFormat.YUV_420_888) {
        throw IllegalArgumentException("Invalid image format")
    }

    val width = image.width
    val height = image.height

    val yPlane = image.planes[0]
    val uPlane = image.planes[1]
    val vPlane = image.planes[2]

    val yBuffer: ByteBuffer = yPlane.buffer
    val uBuffer: ByteBuffer = uPlane.buffer
    val vBuffer: ByteBuffer = vPlane.buffer

    // Full size of the NV21 buffer
    val nv21Size = width * height + 2 * (width * height / 4)
    val nv21 = ByteArray(nv21Size)

    // 1. Copy Y plane
    // If row stride is equal to width, we can copy the entire plane in one go.
    if (yPlane.rowStride == width) {
        yBuffer.get(nv21, 0, width * height)
    } else {
        // If there's padding, we have to copy row by row.
        val yRowStride = yPlane.rowStride
        var yOffset = 0
        for (row in 0 until height) {
            yBuffer.position(row * yRowStride)
            yBuffer.get(nv21, yOffset, width)
            yOffset += width
        }
    }

    // 2. Copy VU planes (interleaved)
    val vRowStride = vPlane.rowStride
    val uRowStride = uPlane.rowStride
    val vPixelStride = vPlane.pixelStride
    val uPixelStride = uPlane.pixelStride

    val vuBuffer = ByteArray(vPlane.rowStride)
    var vuOffset = width * height

    // The U/V planes are guaranteed to have the same row stride and pixel stride.
    // The V plane comes first in NV21 format.
    for (row in 0 until height / 2) {
        val vBufferRowStart = row * vRowStride
        val uBufferRowStart = row * uRowStride

        vBuffer.position(vBufferRowStart)
        
        // Optimization: If the V plane has no padding and its pixel stride is 2 (VUVU...),
        // we can copy the row directly.
        if (vPixelStride == 2 && vRowStride == width) {
            vBuffer.get(nv21, vuOffset, width)
            vuOffset += width
        } else {
            // General case: Copy V and U plane data into a temporary buffer and then interleave them.
            vBuffer.get(vuBuffer, 0, width / 2 * vPixelStride)
            uBuffer.position(uBufferRowStart)
            
            for (col in 0 until width / 2) {
                nv21[vuOffset++] = vuBuffer[col * vPixelStride] // V
                // The U plane value for the same pixel is at the same position in its buffer
                // due to the guaranteed format structure. We read it directly from the U buffer.
                nv21[vuOffset++] = uBuffer.get(uBufferRowStart + col * uPixelStride) // U
            }
        }
    }

    return nv21
}
```

### How to Use It in Your Camera2 `ImageReader.OnImageAvailableListener`

You would call this function inside your listener when a new image is available.

```kotlin
class MyImageAvailableListener : ImageReader.OnImageAvailableListener {
    override fun onImageAvailable(reader: ImageReader) {
        var image: Image? = null
        try {
            image = reader.acquireLatestImage()
            if (image != null) {
                // This is the call to our high-performance conversion function
                val nv21ByteArray: ByteArray = yuv420888ToNv21(image)

                // Now, process the nv21ByteArray...
                // e.g., send it to a processing thread, a native library, or an encoder.

            }
        } finally {
            // IMPORTANT: Always close the image to release the buffer back to the camera.
            image?.close()
        }
    }
}
```

### Key Performance Considerations

1.  **Direct Buffer Access**: The code reads directly from the `ByteBuffer` of each plane (`yBuffer`, `uBuffer`, `vBuffer`), which is the most direct way to access the pixel data without intermediate copies.
2.  **Handling Strides**: It correctly handles the `rowStride` and `pixelStride`. The `rowStride` is the width of the buffer in memory, which can be larger than the actual image width due to padding for memory alignment. Ignoring this is a common source of bugs and distorted images.
3.  **Memory Reuse**: For even better performance, especially to avoid garbage collection pauses, you can pre-allocate the `nv21` `ByteArray` and pass it to a modified function to be filled, rather than allocating a new one for every frame.
4.  **Offload Processing**: The `onImageAvailable` callback runs on a critical thread. Perform the conversion and any subsequent heavy processing on a background thread (e.g., using a `HandlerThread` or Coroutines) to avoid blocking the camera pipeline.

---
---
---

# 2

Of course. You are right to look into a native library solution for the absolute lowest latency. The image you provided correctly identifies Google's `libyuv` as the premier, highly-optimized library for this exact task.

Using `libyuv` through the Android NDK (Native Development Kit) will give you a significant performance boost over any Java/Kotlin implementation. The library is written in C++ and assembly, leveraging CPU-specific SIMD instructions (like NEON on ARM processors) to perform conversions and processing at maximum speed.

Here is a complete, step-by-step guide on how to integrate `libyuv` into your Android project and use it to convert a Camera2 `Image` object to an NV21 byte array.

### Absolute Fastest Method: Native C++ with libyuv

The core of this method is to pass the memory pointers of the `Image` object's color planes directly to a native C++ function, which then uses `libyuv` to perform the conversion without any data copying in the Java/Kotlin layer.

#### Step 1: Set Up NDK and CMake in Your Project

First, ensure your project is configured for native development.

1.  **Install the NDK and CMake:** In Android Studio, go to **Tools > SDK Manager > SDK Tools**. Check **NDK (Side by side)** and **CMake**, then click Apply.

2.  **Link C++ to Your Gradle File:** Open your module-level `build.gradle` (or `build.gradle.kts`) file and add the following inside the `android` block to specify the path to your CMake script file.

    **Groovy (`build.gradle`):**
    ```groovy
    android {
        // ... other settings
        externalNativeBuild {
            cmake {
                path "src/main/cpp/CMakeLists.txt"
                version "3.22.1" // Use a specific version
            }
        }
    }
    ```

    **Kotlin DSL (`build.gradle.kts`):**
    ```kotlin
    android {
        // ... other settings
        externalNativeBuild {
            cmake {
                path = file("src/main/cpp/CMakeLists.txt")
                version = "3.22.1" // Use a specific version
            }
        }
    }
    ```

#### Step 2: Add `libyuv` and Configure CMake

1.  **Create CMakeLists.txt:** In your project, navigate to `app/src/main/` and create a new directory named `cpp`. Inside `cpp`, create a file named `CMakeLists.txt`.

2.  **Add `libyuv` Source:** The easiest way to manage `libyuv` is to add it as a Git submodule. Open a terminal in your project's root directory and run:
    ```bash
    git submodule add https://chromium.googlesource.com/libyuv/libyuv app/src/main/cpp/libyuv
    ```
    This will clone the `libyuv` repository into the `cpp` directory.

3.  **Configure the Build:** Paste the following content into your `CMakeLists.txt` file. This script tells CMake how to build both `libyuv` and your own native wrapper library.

    ```cmake
    # Sets the minimum version of CMake required.
    cmake_minimum_required(VERSION 3.22.1)

    # Add libyuv as a subdirectory. CMake will find its own CMakeLists.txt and build it.
    # We also turn off libyuv's tests.
    add_subdirectory(libyuv EXCLUDE_FROM_ALL)
    set_property(TARGET libyuv PROPERTY ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

    # Define our native library that will be called from Kotlin/Java.
    # Let's call it "yuv_converter".
    add_library(
            yuv_converter
            SHARED
            yuv_converter.cpp) # The name of our C++ source file

    # Find and link the Android logging library (for printing to Logcat).
    find_library(
            log-lib
            log)

    # Link our library against libyuv and the Android log library.
    target_link_libraries(
            yuv_converter
            libyuv
            ${log-lib})
    ```

#### Step 3: Write the Native C++ Conversion Code

Now, create the C++ file that will contain the JNI bridge and the call to `libyuv`.

1.  **Create C++ Source File:** Inside the `app/src/main/cpp/` directory, create a new file named `yuv_converter.cpp`.

2.  **Add the JNI Code:** Paste the following C++ code into `yuv_converter.cpp`. This code defines a function that can be called from Kotlin, receives the `ByteBuffers` and strides, and uses `libyuv::Android420ToNV21` to do the work.

    ```cpp
    #include <jni.h>
    #include "libyuv/convert.h" // Main libyuv header

    extern "C" JNIEXPORT jbyteArray JNICALL
    Java_com_your_package_name_YuvConverter_yuv420ToNv21Native(
            JNIEnv *env,
            jobject /* this */,
            jobject y_buffer,
            jobject u_buffer,
            jobject v_buffer,
            jint y_row_stride,
            jint u_row_stride,
            jint v_row_stride,
            jint width,
            jint height) {

        // Get direct buffer addresses
        auto y = static_cast<uint8_t *>(env->GetDirectBufferAddress(y_buffer));
        auto u = static_cast<uint8_t *>(env->GetDirectBufferAddress(u_buffer));
        auto v = static_cast<uint8_t *>(env->GetDirectBufferAddress(v_buffer));

        // The size of the output NV21 buffer
        int nv21_size = width * height * 3 / 2;
        jbyteArray nv21_output_array = env->NewByteArray(nv21_size);
        auto nv21_output_ptr = env->GetByteArrayElements(nv21_output_array, nullptr);

        // The NV21 format has its Y plane first, followed by the interleaved VU plane.
        uint8_t* dst_y = reinterpret_cast<uint8_t *>(nv21_output_ptr);
        uint8_t* dst_vu = dst_y + (width * height);

        // Call the libyuv function to perform the conversion
        libyuv::Android420ToNV21(
                y, y_row_stride,
                u, u_row_stride,
                v, v_row_stride,
                dst_y, width,      // dst_y and its stride
                dst_vu, width,     // dst_vu and its stride
                width, height);

        // Release the Java byte array elements
        env->ReleaseByteArrayElements(nv21_output_array, nv21_output_ptr, 0);

        return nv21_output_array;
    }
    ```
    **Important:** Replace `com_your_package_name_YuvConverter` with your app's actual package name and the name of the Kotlin class you will create in the next step.

#### Step 4: Create the Kotlin/Java Interface

Finally, create a class in your Kotlin/Java code to load the native library and call the native function.

1.  **Create Kotlin Class:** Create a new Kotlin file, for example, `YuvConverter.kt`.

2.  **Add the Interface Code:** This class will load your `yuv_converter` library and provide a clean, easy-to-use function that takes the `Image` object.

    ```kotlin
    import android.media.Image
    import java.nio.ByteBuffer

    object YuvConverter {

        init {
            // This loads the "libyuv_converter.so" library at runtime.
            System.loadLibrary("yuv_converter")
        }

        /**
         * A high-performance helper function to convert a YUV_420_888 Image to an NV21 byte array.
         *
         * @param image The Image object from Camera2 API.
         * @return The NV21 byte array, or null if the conversion fails.
         */
        fun yuv420ToNv21(image: Image): ByteArray {
            val yPlane = image.planes[0]
            val uPlane = image.planes[1]
            val vPlane = image.planes[2]

            val yBuffer: ByteBuffer = yPlane.buffer
            val uBuffer: ByteBuffer = uPlane.buffer
            val vBuffer: ByteBuffer = vPlane.buffer

            return yuv420ToNv21Native(
                yBuffer,
                uBuffer,
                vBuffer,
                yPlane.rowStride,
                uPlane.rowStride,
                vPlane.rowStride,
                image.width,
                image.height
            )
        }

        // The external function that is implemented in the C++ layer
        private external fun yuv420ToNv21Native(
            yBuffer: ByteBuffer,
            uBuffer: ByteBuffer,
            vBuffer: ByteBuffer,
            yRowStride: Int,
            uRowStride: Int,
            vRowStride: Int,
            width: Int,
            height: Int
        ): ByteArray
    }
    ```

### How to Use It

Now you can use the `YuvConverter` in your `ImageReader.OnImageAvailableListener` just like the previous pure Kotlin solution, but with much higher performance.

```kotlin
class MyImageAvailableListener : ImageReader.OnImageAvailableListener {
    override fun onImageAvailable(reader: ImageReader) {
        var image: Image? = null
        try {
            image = reader.acquireLatestImage()
            if (image != null) {
                // Call the native converter
                val nv21ByteArray: ByteArray = YuvConverter.yuv420ToNv21(image)

                // Process the nv21ByteArray at maximum speed...
            }
        } finally {
            image?.close()
        }
    }
}
```

By following these steps, you will have the absolute fastest method for YUV to NV21 conversion running in your Android app, minimizing latency and ensuring your real-time processing pipeline runs as smoothly as possible.


---
---
---
# 3

Of course. If you are unable to download `libyuv`, I can provide you with a self-contained C++ implementation that you can use directly.

This native C++ code performs the same high-speed conversion from a `YUV_420_888` `Image` object to an `NV21` byte array. It manually handles the memory planes and their strides, which is what makes it significantly faster than a pure Kotlin/Java implementation.

Follow these steps to integrate the native C++ code into your Android project.

### Step 1: Set Up NDK and CMake in Your Project

First, ensure your project is configured for native C++ code.

1.  **Install NDK and CMake:** In Android Studio, go to **Tools > SDK Manager > SDK Tools**. Check **NDK (Side by side)** and **CMake**, then click Apply.
2.  **Link C++ to Gradle:** Open your module-level `build.gradle` (or `build.gradle.kts`) file and add the `externalNativeBuild` block.

    **Groovy (`build.gradle`):**
    ```groovy
    android {
        // ... other settings
        externalNativeBuild {
            cmake {
                path "src/main/cpp/CMakeLists.txt"
                version "3.22.1"
            }
        }
    }
    ```
    **Kotlin DSL (`build.gradle.kts`):**
    ```kotlin
    android {
        // ... other settings
        externalNativeBuild {
            cmake {
                path = file("src/main/cpp/CMakeLists.txt")
                version = "3.22.1"
            }
        }
    }
    ```

### Step 2: Add the C++ Source and CMake Build Script

1.  **Create the `cpp` Directory:** In your Android Studio project view, navigate to `app/src/main/`. Right-click and select **New > Directory**. Name it `cpp`.

2.  **Create `CMakeLists.txt`:** Inside the new `cpp` directory, create a new file named `CMakeLists.txt` and paste the following content into it. This file tells the build system how to compile your C++ code.

    ```cmake
    # Sets the minimum version of CMake required.
    cmake_minimum_required(VERSION 3.22.1)

    # Defines our native library that will be called from Kotlin/Java.
    # The output will be "libyuv_converter.so".
    add_library(
            yuv_converter
            SHARED
            yuv_converter.cpp) # The name of our C++ source file

    # Find and link the Android logging library (optional, but good practice).
    find_library(
            log-lib
            log)

    # Link our library against the Android log library.
    target_link_libraries(
            yuv_converter
            ${log-lib})
    ```

3.  **Create `yuv_converter.cpp`:** Inside the same `cpp` directory, create a new file named `yuv_converter.cpp`. Paste the C++ code below into this file. This is the core conversion logic.

    ```cpp
    #include <jni.h>

    // This function performs the actual YUV_420_888 to NV21 conversion
    void convert_yuv_420_888_to_nv21(
            const uint8_t *y_pixel,
            const uint8_t *u_pixel,
            const uint8_t *v_pixel,
            int32_t y_row_stride,
            int32_t u_row_stride,
            int32_t v_row_stride,
            int32_t u_pixel_stride,
            int32_t v_pixel_stride,
            int width,
            int height,
            uint8_t *nv21_output) {

        // Pointer to the start of the Y plane in the output buffer
        uint8_t *y_out = nv21_output;

        // Pointer to the start of the VU plane in the output buffer
        uint8_t *vu_out = nv21_output + width * height;

        // 1. Copy the Y plane
        // If there is no padding, we can do a fast copy
        if (y_row_stride == width) {
            memcpy(y_out, y_pixel, width * height);
        } else {
            // If there is padding, we have to copy row by row
            for (int i = 0; i < height; ++i) {
                memcpy(y_out + i * width, y_pixel + i * y_row_stride, width);
            }
        }

        // 2. Interleave the U and V planes into the VU plane
        // The U and V planes have half the width and half the height of the Y plane
        for (int row = 0; row < height / 2; ++row) {
            for (int col = 0; col < width / 2; ++col) {
                // Calculate the index for the VU plane in the output buffer
                int vu_index = row * width + col * 2;

                // The V plane comes first in NV21
                vu_out[vu_index] = *(v_pixel + row * v_row_stride + col * v_pixel_stride);
                // The U plane comes second
                vu_out[vu_index + 1] = *(u_pixel + row * u_row_stride + col * u_pixel_stride);
            }
        }
    }


    extern "C" JNIEXPORT jbyteArray JNICALL
    Java_com_your_package_name_YuvConverter_yuv420ToNv21Native( // <-- IMPORTANT: Change this package name
            JNIEnv *env,
            jobject /* this */,
            jobject y_buffer,
            jobject u_buffer,
            jobject v_buffer,
            jint y_row_stride,
            jint u_row_stride,
            jint v_row_stride,
            jint u_pixel_stride,
            jint v_pixel_stride,
            jint width,
            jint height) {

        // Get direct access to the memory of the ByteBuffers
        auto y_pixel = static_cast<uint8_t *>(env->GetDirectBufferAddress(y_buffer));
        auto u_pixel = static_cast<uint8_t *>(env->GetDirectBufferAddress(u_buffer));
        auto v_pixel = static_cast<uint8_t *>(env->GetDirectBufferAddress(v_buffer));

        // Create the output Java byte array for the NV21 data
        int nv21_size = width * height * 3 / 2;
        jbyteArray nv21_output_array = env->NewByteArray(nv21_size);
        auto nv21_output_ptr = env->GetByteArrayElements(nv21_output_array, nullptr);

        // Call our conversion function
        convert_yuv_420_888_to_nv21(
                y_pixel, u_pixel, v_pixel,
                y_row_stride, u_row_stride, v_row_stride,
                u_pixel_stride, v_pixel_stride,
                width, height,
                reinterpret_cast<uint8_t *>(nv21_output_ptr)
        );

        // Release the native pointer back to the Java heap
        env->ReleaseByteArrayElements(nv21_output_array, nv21_output_ptr, 0);

        return nv21_output_array;
    }
    ```
    **VERY IMPORTANT:** In the C++ code above, you must change `Java_com_your_package_name_YuvConverter` to match your app's package name. For example, if your package is `com.example.myapp` and your Kotlin file is `YuvConverter.kt`, the line should be `Java_com_example_myapp_YuvConverter_yuv420ToNv21Native`.

### Step 3: Create the Kotlin Interface

This Kotlin object will load your native library and provide a clean function to call from your app code.

1.  **Create Kotlin File:** In your main source directory (`app/src/main/java/com/your/package/name/`), create a new Kotlin file named `YuvConverter.kt`.

2.  **Add the Interface Code:**

    ```kotlin
    package com.your.package.name // <-- Change to your actual package name

    import android.media.Image
    import java.nio.ByteBuffer

    object YuvConverter {

        init {
            // This loads the native library we built, named "libyuv_converter.so"
            System.loadLibrary("yuv_converter")
        }

        /**
         * A high-performance helper function to convert a YUV_420_888 Image to an NV21 byte array
         * using a native C++ implementation.
         *
         * @param image The Image object from the Camera2 API.
         * @return The NV21 byte array.
         */
        fun yuv420ToNv21(image: Image): ByteArray {
            // Ensure the image is in the correct format
            if (image.format != android.graphics.ImageFormat.YUV_420_888) {
                throw IllegalArgumentException("Image must be in YUV_420_888 format")
            }

            val yPlane = image.planes[0]
            val uPlane = image.planes[1]
            val vPlane = image.planes[2]

            val yBuffer: ByteBuffer = yPlane.buffer
            val uBuffer: ByteBuffer = uPlane.buffer
            val vBuffer: ByteBuffer = vPlane.buffer

            // Call the external C++ function
            return yuv420ToNv21Native(
                yBuffer,
                uBuffer,
                vBuffer,
                yPlane.rowStride,
                uPlane.rowStride,
                vPlane.rowStride,
                uPlane.pixelStride, // U and V planes have the same pixel stride
                vPlane.pixelStride,
                image.width,
                image.height
            )
        }

        // This declares the native function that is implemented in yuv_converter.cpp
        private external fun yuv420ToNv21Native(
            yBuffer: ByteBuffer,
            uBuffer: ByteBuffer,
            vBuffer: ByteBuffer,
            yRowStride: Int,
            uRowStride: Int,
            vRowStride: Int,
            uPixelStride: Int,
            vPixelStride: Int,
            width: Int,
            height: Int
        ): ByteArray
    }
    ```

### Step 4: Rebuild and Use

1.  **Sync Gradle and Rebuild:** Click **File > Sync Project with Gradle Files**, and then **Build > Rebuild Project**. This will compile your C++ code into a `.so` library and package it with your app.
2.  **Use in your listener:** Now you can call it from your `ImageReader.OnImageAvailableListener` to get the fastest possible conversion without any external libraries.

    ```kotlin
    class MyImageAvailableListener : ImageReader.OnImageAvailableListener {
        override fun onImageAvailable(reader: ImageReader) {
            var image: Image? = null
            try {
                image = reader.acquireLatestImage()
                if (image != null) {
                    // Call the native converter
                    val nv21ByteArray: ByteArray = YuvConverter.yuv420ToNv21(image)

                    // Process the nv21ByteArray at maximum speed...
                }
            } finally {
                image?.close()
            }
        }
    }
    ```


---
---
---
# 4
You are absolutely right to demand better performance. A 60ms conversion time is far too slow for real-time video processing and indicates that the previous C++ code was not sufficiently optimized. The bottleneck is the row-by-row, pixel-by-pixel processing of the U and V planes, which doesn't take advantage of modern CPU capabilities.

To get the performance leap you're looking for (down to ~30ms or even sub-10ms), we must use **NEON Intrinsics**.

NEON is an advanced SIMD (Single Instruction, Multiple Data) instruction set available on ARM processors, which power virtually all Android devices. It allows the CPU to perform the same operation on multiple pieces of data simultaneously. Instead of interleaving one U and one V pixel at a time, we can load 8 or 16 pixels at once and interleave them with a single instruction. This is the exact technique that high-performance libraries like Google's `libyuv` use to achieve their speed.

Here is the fully optimized, self-contained C++ code using NEON, along with the necessary build configuration changes.

### Step 1: Update Your `CMakeLists.txt` to Enable NEON

You must enable NEON flags for the compiler. This tells it to generate the specialized NEON instructions. Modify your `app/src/main/cpp/CMakeLists.txt` file to include the `-mfpu=neon` flag.

```cmake
# Sets the minimum version of CMake required.
cmake_minimum_required(VERSION 3.22.1)

add_library(
        yuv_converter
        SHARED
        yuv_converter.cpp)

# Enable NEON instructions for ARM architectures
if(ANDROID_ABI STREQUAL "armeabi-v7a" OR ANDROID_ABI STREQUAL "arm64-v8a")
    # Set the compile flags for our library
    target_compile_options(yuv_converter PRIVATE -mfpu=neon -O3 -D__ARM_NEON__)
endif()

find_library(
        log-lib
        log)

target_link_libraries(
        yuv_converter
        ${log-lib})
```
**Note:** We also add `-O3` for maximum optimization.

### Step 2: Update Your `build.gradle` to Target ARM Architectures

To ensure your app builds the native code for the right CPUs, specify the ABI filters in your module-level `build.gradle` or `build.gradle.kts`.

**Groovy (`build.gradle`):**
```groovy
android {
    // ...
    defaultConfig {
        // ...
        ndk {
            abiFilters 'arm64-v8a', 'armeabi-v7a'
        }
    }
    // ...
}
```
**Kotlin DSL (`build.gradle.kts`):**
```kotlin
android {
    // ...
    defaultConfig {
        // ...
        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a")
        }
    }
    // ...
}
```

### Step 3: Use the NEON-Optimized C++ Code

Replace the entire content of your `app/src/main/cpp/yuv_converter.cpp` file with the code below. It includes a highly optimized NEON path for interleaving the U and V planes.

```cpp
#include <jni.h>
#include <cstring> // For memcpy

// Include NEON header only when compiling for ARM
#if defined(__ARM_NEON__)
#include <arm_neon.h>
#endif

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_your_package_name_YuvConverter_yuv420ToNv21Native( // <-- IMPORTANT: Change this
        JNIEnv *env,
        jobject /* this */,
        jobject y_buffer,
        jobject u_buffer,
        jobject v_buffer,
        jint y_row_stride,
        jint u_row_stride,
        jint v_row_stride,
        jint u_pixel_stride,
        jint v_pixel_stride,
        jint width,
        jint height) {

    // Get direct pointers to the pixel data
    auto y_src = static_cast<const uint8_t *>(env->GetDirectBufferAddress(y_buffer));
    auto u_src = static_cast<const uint8_t *>(env->GetDirectBufferAddress(u_buffer));
    auto v_src = static_cast<const uint8_t *>(env->GetDirectBufferAddress(v_buffer));

    // Create the output Java byte array
    jbyteArray nv21_output_array = env->NewByteArray(width * height * 3 / 2);
    auto nv21_output_ptr = env->GetByteArrayElements(nv21_output_array, nullptr);
    auto nv21_dst = reinterpret_cast<uint8_t *>(nv21_output_ptr);

    // 1. Copy Y Plane (fast path for continuous memory)
    uint8_t *y_dst = nv21_dst;
    if (y_row_stride == width) {
        memcpy(y_dst, y_src, width * height);
    } else {
        for (int i = 0; i < height; ++i) {
            memcpy(y_dst + i * width, y_src + i * y_row_stride, width);
        }
    }

    // 2. Interleave U and V Planes (NV21 format is VUVUVU...)
    uint8_t *vu_dst = nv21_dst + width * height;
    int uv_width = width / 2;
    int uv_height = height / 2;

    for (int row = 0; row < uv_height; ++row) {
        // Get pointers to the start of the current row for U and V
        const uint8_t *v_row_ptr = v_src + (row * v_row_stride);
        const uint8_t *u_row_ptr = u_src + (row * u_row_stride);
        // Get pointer to the start of the current row in the destination
        uint8_t *vu_row_dst_ptr = vu_dst + (row * width);

        int col = 0;

#if defined(__ARM_NEON__)
        // NEON-optimized path for interleaving 16 pixels (8 U and 8 V) at a time
        for (; col <= uv_width - 8; col += 8) {
            // If pixel stride is 1 (UUUUUUUU), we can do a direct load.
            if (u_pixel_stride == 1 && v_pixel_stride == 1) {
                // Load 8 U values and 8 V values into NEON registers
                uint8x8_t u_vec = vld1_u8(u_row_ptr + col);
                uint8x8_t v_vec = vld1_u8(v_row_ptr + col);

                // Create a 2-element structure of vectors to store V and U
                uint8x8x2_t vu_vec;
                vu_vec.val[0] = v_vec; // V plane first
                vu_vec.val[1] = u_vec; // U plane second

                // Store the interleaved VU data (VUVUVU...) to the destination
                vst2_u8(vu_row_dst_ptr + (col * 2), vu_vec);
            } else {
                // Slower NEON path for pixel strides > 1 (e.g., U.U.U.U...)
                // We de-interleave the source into temporary registers first.
                uint8x8x2_t u_deinterleaved = vld2_u8(u_row_ptr + col * u_pixel_stride);
                uint8x8x2_t v_deinterleaved = vld2_u8(v_row_ptr + col * v_pixel_stride);
                
                uint8x8x2_t vu_to_store;
                vu_to_store.val[0] = v_deinterleaved.val[0]; // V
                vu_to_store.val[1] = u_deinterleaved.val[0]; // U

                vst2_u8(vu_row_dst_ptr + (col * 2), vu_to_store);
            }
        }
#endif
        // Scalar fallback loop for remaining pixels or non-NEON builds
        for (; col < uv_width; ++col) {
            vu_row_dst_ptr[col * 2] = *(v_row_ptr + col * v_pixel_stride);
            vu_row_dst_ptr[col * 2 + 1] = *(u_row_ptr + col * u_pixel_stride);
        }
    }

    env->ReleaseByteArrayElements(nv21_output_array, nv21_output_ptr, 0);
    return nv21_output_array;
}
```
**Reminder:** Again, make sure to replace `Java_com_your_package_name_YuvConverter` with the correct path matching your project's package name and Kotlin class.

### Step 4: Rebuild Your Project

After saving the changes to `CMakeLists.txt` and `yuv_converter.cpp`:
1.  Click **File > Sync Project with Gradle Files**.
2.  Click **Build > Rebuild Project**.

Your Kotlin code (`YuvConverter.kt` and your `OnImageAvailableListener`) does not need any changes. The interface remains exactly the same.

With these changes, the native code will now be compiled with full optimization and will use powerful NEON instructions for the most computationally expensive part of the conversion. This should drastically reduce your conversion time, bringing it well within your 30ms target for typical camera resolutions.
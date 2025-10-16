Guide: Creating a Single Android SDK (Fat AAR) from Multiple Modules
This guide will walk you through the process of bundling multiple Android library modules into a single .aar file. This approach simplifies distribution and hides your project's internal module structure from the end-user.
The end goal is to have a single module (which we'll call :sdk) that aggregates all your other library modules (:core, :capture, :network, etc.) into one artifact.
Step 1: Create a New "Aggregator" Module
First, we need a dedicated Android Library module that will serve as the container for your final SDK.
 * In Android Studio, go to File > New > New Module....
 * Select Android Library.
 * Name the module sdk and configure it with your desired package name (e.g., com.yourcompany.sdk).
 * Click Finish.
This :sdk module will not contain any code. Its sole purpose is to define dependencies and run the custom task that builds the final package.
Step 2: Configure Dependencies for the :sdk Module
Now, you need to tell the :sdk module about all the other library modules it needs to bundle.
In the build.gradle.kts (or build.gradle) file of your new :sdk module, add dependencies for all the libraries you want to include.
File: sdk/build.gradle.kts
plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.yourcompany.sdk"
    compileSdk = 34 // Use your project's compileSdk

    defaultConfig {
        minSdk = 24 // Use your project's minSdk
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = true // Enable obfuscation and shrinking
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // This is crucial for defining the public API
            consumerProguardFile("consumer-rules.pro")
        }
    }
    // Other configurations like compileOptions, kotlinOptions...
}

dependencies {
    // Add all your library modules here.
    // The 'api' configuration ensures that the public methods of :core are exposed.
    api(project(":core"))

    // The rest can be 'implementation' as they are internal.
    implementation(project(":capture"))
    implementation(project(":network"))
    implementation(project(":security"))
    implementation(project(":embedding"))
    implementation(project(":utility"))
}

Step 3: Define the Public API and Hide Internals
This is a critical step to ensure users can only access the classes from :core that you intend to expose. We will use ProGuard/R8 rules to achieve this.
 * In your :sdk module, create a file named consumer-rules.pro.
 * Add rules to this file to -keep only the public classes and methods from your :core module. Everything else will be obfuscated and can be removed by the consumer's app if unused (code shrinking).
File: sdk/consumer-rules.pro
# This file defines the public API of your SDK.
# Only the classes, methods, and fields that match these rules will be
# guaranteed to be kept and not renamed.

# Example: Keep all public classes and their public members in the 'api' package of your :core module.
# Adjust the package name to match your actual public API structure.
-keep public class com.yourcompany.core.api.** {
    public *;
}

# If you have public data classes or models, you might need to keep them as well.
# Example:
# -keep public class com.yourcompany.core.models.** { *; }

# IMPORTANT: Everything else from :core, :capture, :network, etc., will be
# obfuscated and potentially removed if not reachable from the code you "keep" above.
# This is how you hide the internal implementation.

Step 4: Create the Gradle Task to Build the Fat AAR
By default, Gradle does not bundle transitive dependencies into an .aar. We need to create a custom task to manually unpack all the individual .aar files and merge them into a single one.
 * In your :sdk module's directory, create a new file named fat-aar.gradle.
 * Copy the following Gradle task script into this file. This script defines a task called assembleFatAar.
File: sdk/fat-aar.gradle
// This task merges all library dependencies into a single AAR.

// Define the libraries to be merged.
// The task will automatically find these dependencies from the 'release' build type.
def modulesToMerge = [':core', ':capture', ':network', ':security', ':embedding', ':utility']

task assembleFatAar(type: Copy) {
    group = "build"
    description = "Assembles a single AAR file from all library modules."

    // The final AAR will have the name of this :sdk module.
    def aarName = "${project.name}-release.aar"
    from(zipTree(file("build/outputs/aar/${aarName}")))

    doLast {
        // Temporary directory for merging.
        def mergeDir = file("${buildDir}/intermediates/fat-aar-merge/")
        if (mergeDir.exists()) {
            mergeDir.deleteDir()
        }
        mergeDir.mkdirs()

        // 1. Unzip the main AAR from the :sdk module.
        copy {
            from(zipTree(file("build/outputs/aar/${aarName}")))
            into mergeDir
        }

        // 2. Iterate over modules, unzip their AARs, and merge contents.
        modulesToMerge.forEach { moduleName ->
            def moduleProject = project(moduleName)
            def moduleAarFile = file("${moduleProject.buildDir}/outputs/aar/${moduleProject.name}-release.aar")

            if (moduleAarFile.exists()) {
                copy {
                    from(zipTree(moduleAarFile))
                    into mergeDir
                    // Exclude files that can cause conflicts or are unnecessary.
                    exclude("**/R.txt", "**/AndroidManifest.xml", "**/proguard.txt")
                }

                // Merge JAR files into the 'libs' folder.
                copy {
                    from(zipTree(moduleAarFile).matching { include 'classes.jar' })
                    into "${mergeDir}/libs"
                    rename 'classes.jar', "${moduleProject.name}-classes.jar"
                }
            }
        }

        // 3. Delete the old classes.jar from the root, as they are now in /libs
        delete "${mergeDir}/classes.jar"

        // 4. Create the new Fat AAR file.
        def destFile = file("${buildDir}/outputs/aar/fat-sdk-release.aar")
        if (destFile.exists()) {
            destFile.delete()
        }

        ant.zip(destfile: destFile, basedir: mergeDir)

        // Clean up.
        mergeDir.deleteDir()
    }
}

// Make sure the fat AAR task runs after the regular assembleRelease task.
assembleRelease.finalizedBy(assembleFatAar)

 * Now, apply this script from your :sdk module's build.gradle.kts file by adding this line at the bottom:
File: sdk/build.gradle.kts
// ... (rest of the file)

// Apply the custom task script
apply(from = "fat-aar.gradle")

Step 5: Build and locate your SDK
You are now ready to build the final artifact.
 * Open the Gradle terminal in Android Studio or your system's command line.
 * Run the assembleRelease task for the :sdk module.
   ./gradlew :sdk:assembleRelease

 * The custom assembleFatAar task will run automatically after assembleRelease completes.
 * You can find your final, bundled SDK in the following directory:
   sdk/build/outputs/aar/fat-sdk-release.aar
This single .aar file is your distributable SDK. It contains the code and resources from all your library modules, with only the API you defined in consumer-rules.pro being public and unobfuscated.

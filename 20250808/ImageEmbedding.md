To generate image embeddings in Kotlin from a `Bitmap` object obtained from the Camera2 API, you can leverage the MediaPipe Image Embedder task. This task simplifies the process of converting image data into a numerical representation, also known as an embedding.

Here's a step-by-step guide on how to achieve this:

### 1. Set up your project dependencies:

First, you need to add the MediaPipe Tasks Vision library to your `build.gradle` file:

```groovy
dependencies {
    // Other dependencies...
    implementation("com.google.mediapipe:tasks-vision:0.10.9")
}
```

### 2. Add the Image Embedding Model to your project:

You will need a pre-trained image embedding model. A recommended model is MobileNetV3. You can download a suitable model and add it to your project's `assets` folder.

### 3. Create an `ImageEmbedderHelper` class:

For a clean implementation, it's good practice to create a helper class to initialize and manage the `ImageEmbedder`. This class will handle loading the model and running the embedding process.

```kotlin
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.imageembedder.ImageEmbedder
import com.google.mediapipe.tasks.vision.imageembedder.ImageEmbedderResult

class ImageEmbedderHelper(
    private val context: Context,
    private val listener: EmbedderListener
) {

    private var imageEmbedder: ImageEmbedder? = null

    init {
        setupImageEmbedder()
    }

    private fun setupImageEmbedder() {
        val baseOptionsBuilder = BaseOptions.builder().setModelAssetPath("mobilenet_v3_small.tflite")
        val optionsBuilder = ImageEmbedder.ImageEmbedderOptions.builder()
            .setBaseOptions(baseOptionsBuilder.build())
            .setL2Normalize(true)
            .setQuantize(true)
            .setRunningMode(RunningMode.IMAGE)

        try {
            imageEmbedder = ImageEmbedder.createFromOptions(context, optionsBuilder.build())
        } catch (e: Exception) {
            // Handle the error
        }
    }

    fun embed(bitmap: Bitmap) {
        val mpImage = MPImage(bitmap)
        val result = imageEmbedder?.embed(mpImage)
        listener.onResults(result)
    }

    interface EmbedderListener {
        fun onResults(result: ImageEmbedderResult?)
        fun onError(error: String)
    }
}
```

### 4. Convert the Bitmap and Generate Embeddings:

Once you have your `Bitmap` from the Camera2 API, you can use the `ImageEmbedderHelper` to generate the embeddings.

First, you'll need to implement the `EmbedderListener` to receive the results:

```kotlin
class YourActivity : AppCompatActivity(), ImageEmbedderHelper.EmbedderListener {

    private lateinit var imageEmbedderHelper: ImageEmbedderHelper

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        //... your existing code

        imageEmbedderHelper = ImageEmbedderHelper(this, this)
    }

    // This is where you would get your bitmap from Camera2 API
    private fun onImageAvailable(bitmap: Bitmap) {
        imageEmbedderHelper.embed(bitmap)
    }

    override fun onResults(result: ImageEmbedderResult?) {
        // Process the embedding results
        result?.let {
            val embedding = it.embeddings().first().embedding()
            // The 'embedding' is a float array representing the image
        }
    }

    override fun onError(error: String) {
        // Handle any errors
    }
}
```

The core of the process is converting the `Bitmap` to an `MPImage` and then calling the `embed` function. This function will return an `ImageEmbedderResult` which contains a list of embeddings. Each embedding is a feature vector that numerically represents the input image.

This approach of using MediaPipe provides a straightforward and efficient way to integrate image embedding capabilities into your Kotlin-based Android application. The generated embeddings can then be used for various tasks like image similarity comparison, image classification, and visual search.
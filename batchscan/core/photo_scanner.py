# pip install accelerate

import base64
import os
import time
from io import BytesIO

import requests
import torch
from PIL import Image
from transformers import AutoProcessor, Gemma3ForConditionalGeneration


class PhotoScanner:
    """
    A class for scanning and analyzing images using the Gemma-3 model.
    Processes images to extract descriptive information.
    """
    
    questions_to_ask = {
        "q1": "give exactly one sentence which describes the scene in the image in a neutral way",
        "q2": "give a comma separated list of keywords that describe the image",
       # "q3": "what is the mood of the image",
       # "q4": "give a single possible title for this image",
    }

    def __init__(self, model_id="google/gemma-3-4b-it"):
        """
        Initialize the PhotoScanner with a specified model.
        
        Args:
            model_id (str): The identifier of the model to use
        """
        self.model_id = model_id
        self.model = None
        self.processor = None
    
    def load_model(self):
        """
        Load the Gemma-3 model and processor.
        """
        #print(f"Loading model: {self.model_id}")
        self.model = Gemma3ForConditionalGeneration.from_pretrained(
            self.model_id, device_map="auto"
        ).eval()
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        #print("Model loaded successfully")

    def load_image(self, source):
        """
        Load an image from a file path, URL, or base64 string.

        Args:
            source (str): Either a file path, URL, or base64 string

        Returns:
            PIL.Image: The loaded image
        """
        if os.path.isfile(source):
            # Load from local file
            img = Image.open(source)
            max_size = 720
            return self._resize_image_if_needed(img, max_size)
        elif source.startswith("http"):
            # Load from URL
            response = requests.get(source)
            return Image.open(BytesIO(response.content))
        elif source.startswith("data:image"):
            # Extract base64 part from data URI
            base64_str = source.split(",")[1]
            img_data = base64.b64decode(base64_str)
            return Image.open(BytesIO(img_data))
        elif len(source) > 100:
            # Assume it's a raw base64 string
            try:
                img_data = base64.b64decode(source)
                return Image.open(BytesIO(img_data))
            except Exception:
                raise ValueError("Invalid base64 string")
        else:
            raise ValueError("Source must be a file path, URL, or base64 string")
    
    def _resize_image_if_needed(self, img, max_size):
        """
        Resize an image if either dimension exceeds the maximum size.
        
        Args:
            img (PIL.Image): Image to resize
            max_size (int): Maximum width or height
            
        Returns:
            PIL.Image: Resized image if needed, otherwise the original image
        """
        if img.width > max_size:
            # Resize if the image is too large
            img = img.resize((max_size, int(max_size * img.height / img.width)))
        if img.height > max_size:
            img = img.resize((int(max_size * img.width / img.height), max_size))
        return img
    
    def process_single_image(self, imagesource):
        """
        Process a single image and return answers to all questions in questions_to_ask.
        Each question is processed with its own fresh context to optimize processing time.

        Args:
            imagesource: Path, URL, or base64 string of the image to process

        Returns:
            dict: Dictionary containing answers to each question in questions_to_ask
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
            
        starttime = time.time()
        print(f"Processing image: {imagesource}")
        image = self.load_image(imagesource)
        results = {}
        
        # Process each question in the questions_to_ask dictionary with a fresh context
        for key, question in self.questions_to_ask.items():
            substarttime = time.time()
            #print(f"Processing question: {key} : {question}")
            answer = self._process_question(image, question)
            results[key] = answer
            #print(f"Answer: {answer}")
            subendtime = time.time()
            print(f"Question processing time: {subendtime - substarttime:.2f} seconds")
            
        endtime = time.time()
        print(f"Image processing time: {endtime - starttime:.2f} seconds")    
        return results
    
    def _process_question(self, image, question):
        """
        Process a single question about an image.
        
        Args:
            image (PIL.Image): The image to analyze
            question (str): The question to ask about the image
            
        Returns:
            str: The model's answer to the question
        """
        # Create new messages for this question to avoid context build-up
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant."}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": question}
                ],
            },
        ]
        
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device, dtype=torch.bfloat16)

        input_len = inputs["input_ids"].shape[-1]

        with torch.inference_mode():
            generation = self.model.generate(
                **inputs, max_new_tokens=100, do_sample=True, temperature=0.9
            )
            generation = generation[0][input_len:]

        return self.processor.decode(generation, skip_special_tokens=True)

    def check_gpu(self):
        """
        Check if a GPU is available and print the device name.
        """
        if torch.cuda.is_available():
            device = torch.cuda.get_device_name(0)
            print(f"Using GPU: {device}")
        else:
            print("No GPU found, using CPU.")
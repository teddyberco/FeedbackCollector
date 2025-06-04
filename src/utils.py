import nltk
from textblob import TextBlob
import logging
from config import FEEDBACK_CATEGORIES_WITH_KEYWORDS, DEFAULT_CATEGORY

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

NLTK_RESOURCES = {
    'corpora/averaged_perceptron_tagger': 'averaged_perceptron_tagger',
    'tokenizers/punkt': 'punkt',
    'corpora/brown': 'brown' # Brown corpus is often used by TextBlob for NP extraction
}

def download_nltk_resources():
    """Downloads necessary NLTK resources if they are not already present."""
    for resource_path, resource_id in NLTK_RESOURCES.items():
        try:
            nltk.data.find(resource_path)
            logger.info(f"NLTK resource '{resource_id}' already downloaded.")
        except LookupError: # Corrected exception type
            logger.warning(f"NLTK resource '{resource_id}' not found. Attempting to download...")
            try:
                nltk.download(resource_id, quiet=True)
                logger.info(f"Successfully downloaded NLTK resource '{resource_id}'.")
            except Exception as e:
                logger.error(f"Failed to download NLTK resource '{resource_id}': {e}")
                logger.error(
                    "Please try downloading it manually by running Python and typing:\n"
                    "import nltk\n"
                    f"nltk.download('{resource_id}')"
                )
        except Exception as e: # Catch any other lookup errors
            logger.error(f"Error checking NLTK resource '{resource_id}': {e}. Attempting download.")
            try:
                nltk.download(resource_id, quiet=True)
                logger.info(f"Successfully downloaded NLTK resource '{resource_id}'.")
            except Exception as download_e:
                logger.error(f"Failed to download NLTK resource '{resource_id}' after error: {download_e}")

# Call download_nltk_resources when the module is loaded
# This ensures that the resources are checked/downloaded once.
download_nltk_resources()

def generate_feedback_gist(text: str, max_length: int = 150, num_phrases: int = 3) -> str:
    """
    Generates a concise gist or title from feedback text using noun phrase extraction.

    Args:
        text: The feedback text.
        max_length: The maximum desired length for the gist.
        num_phrases: The number of noun phrases to try to combine.

    Returns:
        A string representing the feedback gist.
    """
    if not text or not isinstance(text, str):
        return "No content"

    try:
        blob = TextBlob(text)
        noun_phrases = blob.noun_phrases
        
        if noun_phrases:
            # Take unique noun phrases to avoid repetition if the same phrase appears multiple times early on
            unique_phrases = []
            for phrase in noun_phrases:
                if phrase.lower() not in [p.lower() for p in unique_phrases]:
                    unique_phrases.append(phrase)
            
            selected_phrases = unique_phrases[:num_phrases]
            gist = "... ".join(selected_phrases).strip()
            
            if len(gist) > max_length:
                gist = gist[:max_length-3] + "..."
            elif not gist: # Fallback if selected phrases were empty (e.g. very short phrases)
                gist = text[:max_length-3] + "..." if len(text) > max_length else text
            
            # Capitalize first letter of the gist
            if gist:
                gist = gist[0].upper() + gist[1:]
            return gist if gist else "Summary unavailable"

        else:
            # Fallback if no noun phrases are found
            words = text.split()
            gist = " ".join(words[:10]) # First 10 words
            if len(words) > 10:
                gist += "..."
            return gist if gist else "Summary unavailable"
            
    except Exception as e:
        logger.error(f"Error generating feedback gist: {e}. Falling back to simple truncation.")
        # Fallback in case of any TextBlob/NLTK error
        return text[:max_length-3] + "..." if len(text) > max_length else text

def categorize_feedback(text: str) -> str:
    """
    Categorizes feedback text based on keywords defined in config.
    Returns the name of the first matching category or a default category.
    """
    if not text or not isinstance(text, str):
        return DEFAULT_CATEGORY

    text_lower = text.lower()
    for category_id, category_info in FEEDBACK_CATEGORIES_WITH_KEYWORDS.items():
        for keyword in category_info.get('keywords', []):
            if keyword.lower() in text_lower:
                return category_info['name']
    return DEFAULT_CATEGORY

if __name__ == '__main__':
    # Test cases
    print(f"NLTK Resource Check Complete (see logs above).")
    sample1 = "The user interface is very intuitive and the performance is excellent. I love the new dashboard feature!"
    print(f"Text: {sample1}\nGist: {generate_feedback_gist(sample1)}")

    sample2 = "It crashes frequently on my Android device, especially when I try to upload a file."
    print(f"Text: {sample2}\nGist: {generate_feedback_gist(sample2)}")

    sample3 = "Good."
    print(f"Text: {sample3}\nGist: {generate_feedback_gist(sample3)}")
    
    sample4 = "This is a very long piece of feedback that talks about many different things including the speed, the reliability, the customer service which was not great, and also the pricing model which I think could be improved significantly for small businesses like mine."
    print(f"Text: {sample4}\nGist: {generate_feedback_gist(sample4, num_phrases=3)}")

    sample5 = ""
    print(f"Text: '{sample5}'\nGist: {generate_feedback_gist(sample5)}")

    sample6 = "Login button not working."
    print(f"Text: '{sample6}'\nGist: {generate_feedback_gist(sample6)}")

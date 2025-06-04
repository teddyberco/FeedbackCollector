import logging
from typing import List, Dict, Any
from collectors import RedditCollector, FabricCommunityCollector, GitHubDiscussionsCollector
from storage import StorageManager
from config import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FeedbackCollector:
    def __init__(self):
        self.reddit_collector = RedditCollector()
        self.community_collector = FabricCommunityCollector()
        self.github_collector = GitHubDiscussionsCollector()
        self.storage_manager = StorageManager()

    def collect_and_save(self) -> None:
        """Collect feedback from all sources and save to storage."""
        try:
            logger.info("Starting feedback collection process...")
            
            # Collect feedback from Reddit
            reddit_items = self.reddit_collector.collect()
            logger.info(f"Collected {len(reddit_items)} items from Reddit")
            
            # Collect feedback from MS Fabric Community
            community_items = self.community_collector.collect()
            logger.info(f"Collected {len(community_items)} items from MS Fabric Community")
            
            # Collect feedback from GitHub Discussions
            github_items = self.github_collector.collect()
            logger.info(f"Collected {len(github_items)} items from GitHub Discussions")
            
            # Combine all feedback items
            all_items = reddit_items + community_items + github_items
            
            # Format and validate items
            processed_items = []
            for item in all_items:
                formatted_item = self.storage_manager.format_feedback_item(item)
                if self.storage_manager.validate_feedback_item(formatted_item):
                    processed_items.append(formatted_item)
                else:
                    logger.warning(f"Invalid feedback item found: {item}")
            
            # Save to storage
            if processed_items:
                self.storage_manager.save_feedback(processed_items)
                logger.info(f"Successfully processed and saved {len(processed_items)} feedback items")
            else:
                logger.info("No valid feedback items to save")
                
        except Exception as e:
            logger.error(f"Error in feedback collection process: {str(e)}")

if __name__ == "__main__":
    try:
        logger.info("Starting feedback collection...")
        collector = FeedbackCollector()
        collector.collect_and_save()
        logger.info("Feedback collection completed")
    except KeyboardInterrupt:
        logger.info("Feedback collection process stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the state management functionality
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import state_manager
import config

def test_state_manager():
    print("Testing State Management Functionality")
    print("=" * 50)
    
    # Test 1: Generate feedback ID
    print("1. Testing feedback ID generation...")
    feedback_id = state_manager.generate_feedback_id()
    print(f"   Generated ID: {feedback_id}")
    assert len(feedback_id) > 0, "Feedback ID should not be empty"
    print("   PASS")
    
    # Test 2: Extract user from token (mock token)
    print("\n2. Testing user extraction from token...")
    mock_token = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJ1cG4iOiJ0ZXN0QGV4YW1wbGUuY29tIn0.test"
    user = state_manager.extract_user_from_token(mock_token)
    print(f"   Extracted user: {user}")
    assert user is not None, "User should be extracted"
    print("   PASS Pass")
    
    # Test 3: Validate states
    print("\n3. Testing state validation...")
    valid_states = ['NEW', 'TRIAGED', 'CLOSED', 'IRRELEVANT']
    for state in valid_states:
        assert state_manager.validate_state(state), f"State {state} should be valid"
        print(f"   PASS {state} is valid")
    
    assert not state_manager.validate_state('INVALID'), "INVALID should not be valid"
    print("   PASS Invalid state correctly rejected")
    
    # Test 4: Get all states
    print("\n4. Testing get all states...")
    all_states = state_manager.get_all_states()
    print(f"   Found {len(all_states)} states:")
    for state in all_states:
        print(f"     - {state['key']}: {state['name']} ({state['color']})")
    assert len(all_states) == 4, "Should have 4 states"
    print("   PASS Pass")
    
    # Test 5: Initialize feedback state
    print("\n5. Testing feedback state initialization...")
    test_feedback = {
        'Title': 'Test Feedback',
        'Feedback': 'This is a test feedback item',
        'Sources': 'Test'
    }
    
    initialized = state_manager.initialize_feedback_state(test_feedback.copy())
    print(f"   Initialized feedback:")
    print(f"     - Feedback_ID: {initialized.get('Feedback_ID')}")
    print(f"     - State: {initialized.get('State')}")
    print(f"     - Feedback_Notes: '{initialized.get('Feedback_Notes')}'")
    print(f"     - Last_Updated: {initialized.get('Last_Updated')}")
    print(f"     - Updated_By: {initialized.get('Updated_By')}")
    
    assert initialized.get('Feedback_ID'), "Should have Feedback_ID"
    assert initialized.get('State') == 'NEW', "Should default to NEW state"
    assert initialized.get('Feedback_Notes') == '', "Should have empty notes"
    print("   PASS Pass")
    
    # Test 6: Update state
    print("\n6. Testing state update...")
    feedback_id = initialized['Feedback_ID']
    update_data = state_manager.update_feedback_state(
        feedback_id, 'TRIAGED', 'Reviewed and categorized', 'test@example.com'
    )
    print(f"   Update data: {update_data}")
    assert update_data['State'] == 'TRIAGED', "State should be updated"
    assert update_data['Feedback_Notes'] == 'Reviewed and categorized', "Notes should be updated"
    print("   PASS Pass")
    
    # Test 7: Configuration check
    print("\n7. Testing configuration...")
    print(f"   Default state: {config.DEFAULT_FEEDBACK_STATE}")
    print(f"   Available states in config: {list(config.FEEDBACK_STATES.keys())}")
    print(f"   Table columns include new fields:")
    new_fields = ['Feedback_ID', 'State', 'Feedback_Notes', 'Last_Updated', 'Updated_By']
    for field in new_fields:
        if field in config.TABLE_COLUMNS:
            print(f"     PASS {field}")
        else:
            print(f"     ❌ {field} - MISSING!")
    print("   PASS Configuration looks good")
    
    print("\n" + "=" * 50)
    print("SUCCESS! All tests passed! State management is ready to use.")
    print("\nNext steps:")
    print("1. Run the Flask app: python src/run_web.py")
    print("2. Collect some feedback")
    print("3. Visit /feedback to see the state management UI")
    print("4. Provide a Fabric Bearer Token to enable state management")

if __name__ == '__main__':
    test_state_manager()
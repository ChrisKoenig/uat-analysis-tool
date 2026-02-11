#!/usr/bin/env python3
"""
Test script for regional service availability functionality
"""

from intelligent_context_analyzer import IntelligentContextAnalyzer
import json

def test_databricks_availability():
    """Test Databricks regional availability"""
    print("🧪 Testing Regional Service Availability - Databricks")
    print("=" * 60)
    
    # Initialize the analyzer with live Azure CLI data
    analyzer = IntelligentContextAnalyzer(cache_duration_hours=168, enable_live_data=True)
    
    # Test 1: Get all available regions for Databricks
    print("\n1️⃣ Checking Databricks availability across regions...")
    
    services_to_regions = analyzer.regional_service_availability.get('services_to_regions', {})
    
    # Look for Databricks-related services
    databricks_services = []
    databricks_regions = []
    
    for service_name, regions in services_to_regions.items():
        if 'databricks' in service_name.lower():
            databricks_services.append(service_name)
            databricks_regions.extend(regions)
    
    # Remove duplicates and sort
    databricks_regions = sorted(list(set(databricks_regions)))
    
    if databricks_services:
        print(f"\n📊 Found Databricks services: {databricks_services}")
        print(f"🌍 Available in {len(databricks_regions)} regions:")
        
        # Group regions by continent/area for better readability
        us_regions = [r for r in databricks_regions if 'us' in r]
        europe_regions = [r for r in databricks_regions if any(x in r for x in ['europe', 'uk', 'france', 'germany'])]
        asia_regions = [r for r in databricks_regions if any(x in r for x in ['asia', 'japan', 'korea', 'india'])]
        other_regions = [r for r in databricks_regions if r not in us_regions + europe_regions + asia_regions]
        
        if us_regions:
            print(f"   🇺🇸 US: {', '.join(us_regions)}")
        if europe_regions:
            print(f"   🇪🇺 Europe: {', '.join(europe_regions)}")  
        if asia_regions:
            print(f"   🌏 Asia-Pacific: {', '.join(asia_regions)}")
        if other_regions:
            print(f"   🌐 Other: {', '.join(other_regions)}")
    else:
        print("❌ No Databricks services found in live data")
        print("💡 This could mean:")
        print("   - Azure CLI not available")
        print("   - Using static fallback data")
        print("   - Service name variations not detected")
    
    # Test 2: Test specific region validation
    print(f"\n2️⃣ Testing specific region validation...")
    
    test_regions = ['east us', 'brazil south', 'west europe', 'australia east']
    
    for region in test_regions:
        availability = analyzer.validate_service_region_availability('databricks', region)
        
        status_icon = "✅" if availability['available'] else "❌"
        confidence = availability['confidence']
        
        print(f"{status_icon} Databricks in {region.title()}: Available={availability['available']} (confidence: {confidence:.1f})")
        
        if availability['nearby_regions']:
            print(f"   📍 Nearby alternatives: {', '.join(availability['nearby_regions'][:3])}")
        
        if availability['alternative_services']:
            print(f"   🔄 Alternative services: {', '.join(availability['alternative_services'][:2])}")
    
    # Test 3: Get regional summary for a major region
    print(f"\n3️⃣ Regional service summary for East US...")
    
    summary = analyzer.get_regional_service_summary('east us')
    
    print(f"🌐 Region: {summary['region'].title()}")
    print(f"📊 Total services: {summary['total_services']}")
    print(f"🏆 Top categories: {dict(summary['top_categories'])}")
    
    # Look for analytics services specifically
    analytics_services = summary['categorized_services'].get('analytics', [])
    if analytics_services:
        print(f"📈 Analytics services: {', '.join(analytics_services[:5])}")
    
    # Test 4: Test the actual analyze method with a Databricks query
    print(f"\n4️⃣ Testing full context analysis...")
    
    test_query = "Is Azure Databricks available in Brazil South region? I need to deploy analytics workloads there."
    
    result = analyzer.analyze_context("Databricks availability inquiry", test_query, "medium")
    
    print(f"🔍 Query: '{test_query}'")
    print(f"📂 Category: {result.category}")
    print(f"🎯 Intent: {result.intent}")
    print(f"📝 Summary: {result.context_summary}")
    print(f"🏷️ Entities found:")
    for key, values in result.domain_entities.items():
        if values:
            print(f"   {key}: {values}")
    
    return result

if __name__ == "__main__":
    try:
        result = test_databricks_availability()
        print(f"\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
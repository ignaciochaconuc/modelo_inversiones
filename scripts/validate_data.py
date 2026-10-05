from investment_system.data.validation.validators import validate_feature_target_separation

if __name__ == "__main__":
    validate_feature_target_separation()
    print("Feature and target columns are disjoint.")

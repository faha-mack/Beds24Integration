import datetime
from enum import Enum, EnumMeta
from typing import Literal, Optional
from pydantic import BaseModel

class ListingDetails(BaseModel):
    class Publish(str, Enum):
        """
        Possible values:
        - default: ""
        - yes: "Yes"
        - no: "No"
        """
        yes = "Yes"
        no = "No"
    class PropertyTypeGroup(str, Enum):
        """
        Possible values:
        - default: ""
        - apartments: "Apartments"
        - bnb: "Bnb"
        - boutique_hotels_and_more: "Boutique hotels and more"
        - houses: "Houses"
        - secondary_units: "Secondary units"
        - unique_homes: "Unique homes"
        """
        default = ""
        apartments = "Apartments"
        bnb = "Bnb"
        boutique_hotels_and_more = "Boutique hotels and more"
        houses = "Houses"
        secondary_units = "Secondary units"
        unique_homes = "Unique homes"
    class ListingType(str, Enum):
        """
        Possible values:
        - default: ""
        - private_room: "Private room"
        - shared_room: "Shared room"
        - entire_home: "Entire home"
        """
        default = ""
        private_room = "Private room"
        shared_room = "Shared room"
        entire_home = "Entire home"
    class UpdateAddress(str, Enum):
        """
        Possible values:
        - default: ""
        - yes: "Yes"
        - no: "No"
        """
        yes = "Yes"
        no = "No"
    class PicSource(str, Enum):
        """
        Possible values:
        - default: ""
        - rop: "Room + Offer + Property"
        - ro: "Room + Offer"
        - rp: "Room + Property"
        - r: "Room"
        - p: "Property"
        """
        default = ""
        rop = "Room + Offer + Property"
        ro = "Room + Offer"
        rp = "Room + Property"
        r = "Room"
        p = "Property"
    class BathroomShared(str, Enum):
        """
        Possible values:
        - default: ""
        - private: "Private"
        - host: "Host"
        - family_friends_roommates: "Roommates"
        - other_guests: "Guests"
        - host_family_friends_roommates: "Host + roommates"
        - host_other_guests: "Host + guests"
        - family_friends_roommates_other_guests: "Roommates + guests"
        - host_family_friends_roommates_other_guests: "Host + roommates + guests"
        """
        default = ""
        private = "Private"
        host = "Host"
        family_friends_roommates = "Roommates"
        other_guests = "Guests"
        host_family_friends_roommates = "Host + roommates"
        host_other_guests = "Host + guests"
        family_friends_roommates_other_guests = "Roommates + guests"
        host_family_friends_roommates_other_guests = "Host + roommates + guests"
    class CommonShared(str, Enum):
        """
        Possible values:
        - default: ""
        - private: "Private"
        - host: "Host"
        - family_friends_roommates: "Roommates"
        - other_guests: "Guests"
        - host_family_friends_roommates: "Host + roommates"
        - host_other_guests: "Host + guests"
        - family_friends_roommates_other_guests: "Roommates + guests"
        - host_family_friends_roommates_other_guests: "Host + roommates + guests"
        """
        default = ""
        private = "Private"
        host = "Host"
        family_friends_roommates = "Roommates"
        other_guests = "Guests"
        host_family_friends_roommates = "Host + roommates"
        host_other_guests = "Host + guests"
        family_friends_roommates_other_guests = "Roommates + guests"
        host_family_friends_roommates_other_guests = "Host + roommates + guests"
    class CheckinCategory(str, Enum):
        """
        Possible values:
        - default: ""
        - host_checkin: "Host check-in"
        - doorman_entry: "Doorman entry"
        - keypad: "Keypad"
        - lockbox: "Lockbox"
        - other_checkin: "Other check-in"
        - smartlock: "Smartlock"
        """
        default = ""
        host_checkin = "Host check-in"
        doorman_entry = "Doorman entry"
        keypad = "Keypad"
        lockbox = "Lockbox"
        other_checkin = "Other check-in"
        smartlock = "Smartlock"
    
    publish: Publish
    propertytypegroup: PropertyTypeGroup
    listingtype: ListingType
    updateaddress: UpdateAddress
    picsource: PicSource
    bathroomshared: BathroomShared
    commonshared: CommonShared
    checkincategory: CheckinCategory
    checkindesc: Optional[str]
    housemanual: Optional[str]

class CheckOutInstructions(BaseModel):
    checkoutrk: Optional[str]
    checkouttto: Optional[str]
    checkoutt: Optional[str]
    checkoutlu: Optional[str]
    checkoutgt: Optional[str]
    checkoutar: Optional[str]

class Descriptions(BaseModel):
    class MultiLang(str, Enum):
        """
        Possible values:
        - default: ""
        - no: "No"
        - yes: "Yes"
        """
        default = ""
        no = "No"
        yes = "Yes"
    multilang: MultiLang
    propnameEN: Optional[str]
    summaryEN: Optional[str]
    spaceEN: Optional[str]
    accessEN: Optional[str]
    interactionEN: Optional[str]
    neighborhoodEN: Optional[str]
    transitEN: Optional[str]
    notesEN: Optional[str]

class BookingRules(BaseModel):
    class InstantBookAllow(str, Enum):
        """
        Possible values:
        - default: ""
        - everyone: "Everyone"
        - well_reviewed_guests: "Well reviewed guests"
        - guests_with_verified_identity: "Government id"
        - well_reviewed_guests_with_verified_identity: "Well reviewed guests with government id"
        """
        default = ""
        everyone = "Everyone"
        well_reviewed_guests = "Well reviewed guests"
        guests_with_verified_identity = "Government id"
        well_reviewed_guests_with_verified_identity = "Well reviewed guests with government id"
    class CancelPolicy(str, Enum):
        """
        Possible values:
        - default: ""
        - flexible: "Flexible"
        - moderate: "Moderate"
        - better_strict_with_grace_period: "Firm"
        - strict: "Strict"
        - super_strict_30: "Super strict 30"
        - super_strict_60: "Super strict 60"
        """
        default = ""
        flexible = "Flexible"
        moderate = "Moderate"
        better_strict_with_grace_period = "Firm"
        strict = "Strict"
        super_strict_30 = "Super strict 30"
        super_strict_60 = "Super strict 60" 
    class NonRefundFactor_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 51):
                classdict[f"{i}_percent"] = f"{i}%"
            return super().__new__(metacls, cls, bases, classdict)
    class NonRefundFactor(str, Enum, metaclass=NonRefundFactor_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 50_percent: "1%" to "50%"
        """
        none = "None"

    prebookmsg: Optional[str]
    instantbookallow: InstantBookAllow
    cancelpolicy: CancelPolicy
    nonrefundfactor: NonRefundFactor

class PricingSettings(BaseModel):
    class PricingStrategy(str, Enum):
        """
        Possible values:
        - default: ""
        - per_day_pricing: "Per Day Pricing"
        - per_occupancy_pricing: "Per Occupancy Pricing"
        - rate_plan: "Rate Plans"
        """
        default = ""
        per_day_pricing = "Per Day Pricing"
        per_occupancy_pricing = "Per Occupancy Pricing"
        rate_plan = "Rate Plans"
    class GuestsIncluded_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 51):
                classdict[f"{i}_percent"] = f"{i}"
            return super().__new__(metacls, cls, bases, classdict)
    class GuestsIncluded(str, Enum, metaclass=GuestsIncluded_DynamicEnumMeta):
        """
        Possible values:
        - default: ""
        - 1_percent to 50_percent: "1" to "50"
        """
        default = ""  
    class DatesWithNoPrice(str, Enum):
        """
        Possible values:
        - default: ""
        - makeUnavailable: "Make unavailable"
        - useBasePrice: "Use Base Price"
        """
        default = ""
        makeUnavailable = "Make unavailable"
        useBasePrice = "Use Base Price"  
    class Discounts_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 91):
                classdict[f"{i}_percent"] = f"{i}%"
            return super().__new__(metacls, cls, bases, classdict)
    class TwoDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class ThreeDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class FourDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class FiveDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class SixDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class SevenDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class FourteenDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class TwentyOneDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"
    class TwentyEightDayDiscounts(str, Enum, metaclass=Discounts_DynamicEnumMeta):
        """
        Possible values:
        - none: "None"
        - 1_percent to 90_percent: "1%" to "90%"
        """
        none = "None"  
    class MaxDaysInAdvance_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(30, 331, 30):
                classdict[f"{i}_days"] = f"{i} days"
            return super().__new__(metacls, cls, bases, classdict)
    class MaxDaysInAdvance(str, Enum, metaclass=MaxDaysInAdvance_DynamicEnumMeta):
        """
        Possible values:
        - no_limit: "No Limit"
        - oneyear: "365 days"
        - threeyears: "3 Years"
        - closed: "Closed"
        - 30_days to 330_days: "30 days" to "330 days"
        """
        no_limit = "No Limit"
        oneyear = "365 days"
        threeyears = "3 Years"
        closed = "Closed"
    class AdvanceNotice_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 25):
                classdict[f"{i}_days"] = f"{i}"
            return super().__new__(metacls, cls, bases, classdict)
    class AdvanceNotice(str, Enum, metaclass=AdvanceNotice_DynamicEnumMeta):
        """
        Possible values:
        - zero: "0"
        - fe: "48"
        - st: "72"
        - oxe: "168"
        - 1_days to 24_days: "1" to "24"
        """
        zero = "0"
        fe = "48"
        st = "72"
        oxe = "168"
    class AdvanceNoticeRequest(str, Enum):
        """
        Possible values:
        - allow: "Allow"
        - not_allow: "Not Allowed"
        """
        allow = "Allow"
        not_allow = "Not Allowed"
    class EarlyBirdDaysToCheckIn(str, Enum):
        """
        Possible values:
        - days_360: "360"
        - days_336: "336"
        - days_330: "330"
        - days_308: "308"
        - days_300: "300"
        - days_280: "280"
        - days_270: "270"
        - days_252: "252"
        - days_240: "240"
        - days_224: "224"
        - days_210: "210"
        - days_196: "196"
        - days_180: "180"
        - days_168: "168"
        - days_150: "150"
        - days_140: "140"
        - days_120: "120"
        - days_112: "112"
        - days_90: "90"
        - days_84: "84"
        - days_60: "60"
        - days_56: "56"
        - days_30: "30"
        - days_28: "28"
        """
        days_360 = "360"
        days_336 = "336"
        days_330 = "330"
        days_308 = "308"
        days_300 = "300"
        days_280 = "280"
        days_270 = "270"
        days_252 = "252"
        days_240 = "240"
        days_224 = "224"
        days_210 = "210"
        days_196 = "196"
        days_180 = "180"
        days_168 = "168"
        days_150 = "150"
        days_140 = "140"
        days_120 = "120"
        days_112 = "112"
        days_90 = "90"
        days_84 = "84"
        days_60 = "60"
        days_56 = "56"
        days_30 = "30"
        days_28 = "28"
    class EarlyBirdDiscountPercent_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 51):
                classdict[f"{i}_percent"] = f"{i}%"
            return super().__new__(metacls, cls, bases, classdict)
    class EarlyBirdDiscountPercent(str, Enum, metaclass=EarlyBirdDiscountPercent_DynamicEnumMeta):
        """
        Possible values:
        - zero: "0%"
        - 1_percent to 50_percent: "1%" to "50%"
        """
        zero = "0%"
    class LastMinuteDayToCheckIn_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 29):
                classdict[f"{i}_days"] = f"{i}"
            return super().__new__(metacls, cls, bases, classdict)    
    class LastMinuteDayToCheckIn(str, Enum, metaclass=LastMinuteDayToCheckIn_DynamicEnumMeta):
        """
        Possible values:
        - days_0: "0"
        - 1_days to 28_days: "1" to "28"
        """
        days_0 = "0"  
    class LastMinuteDiscountPercent_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 51):
                classdict[f"{i}_percent"] = f"{i}%"
            return super().__new__(metacls, cls, bases, classdict)
    class LastMinuteDiscountPercent(str, Enum, metaclass=LastMinuteDiscountPercent_DynamicEnumMeta):
        """
        Possible values:
        - zero: "0%"
        - 1_percent to 50_percent: "1%" to "50%"
        """
        zero = "0%"

    extraPersonPrice: Optional[str]
    pricingstrategy: PricingStrategy
    guestsincluded: GuestsIncluded
    dateswithnoprice: DatesWithNoPrice
    twodaydiscounts: TwoDayDiscounts
    threedaydiscounts: ThreeDayDiscounts
    fourdaydiscounts: FourDayDiscounts
    fivedaydiscounts: FiveDayDiscounts
    sixdaydiscounts: SixDayDiscounts
    sevendaydiscounts: SevenDayDiscounts
    fourteendaydiscounts: FourteenDayDiscounts
    twentyonedaydiscounts: TwentyOneDayDiscounts
    twentyeightdaydiscounts: TwentyEightDayDiscounts
    maxdaysinadvance: MaxDaysInAdvance
    advancenotice: AdvanceNotice
    advancenoticerequest: AdvanceNoticeRequest
    earlybirddaystocheckin: EarlyBirdDaysToCheckIn
    earlybirddiscountpercent: EarlyBirdDiscountPercent
    lastminutedaystocheckin: LastMinuteDayToCheckIn
    lastminutediscountpercent: LastMinuteDiscountPercent

class SessionRequest(BaseModel):
    email: Optional[str]

class Custom(BaseModel):
    custom: str
class PropertyDetails(BaseModel):
    class NumberOfFloors_DynamicEnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict):
            for i in range(1, 201):
                classdict[f"{i}"] = f"{i}"
            return super().__new__(metacls, cls, bases, classdict)
    class NumberOfFloors(str, Enum, metaclass=NumberOfFloors_DynamicEnumMeta):
        """
        Possible values:
        - 1 to 200: "1" to "2000"
        """
        pass
    class MaxLengthOfStay(str, Enum):
        thirty = "30"
        fourtyfive = "45"
        sixty = "60"
        seventyfive = "75"
        ninety = "90"
    
    numberoffloors: NumberOfFloors
    maxstay: MaxLengthOfStay

class PropertyProfile(BaseModel): 
    class HostLocation(str, Enum):
        offsite = "Off site"
        onsite = "On site"

    class Company(str, Enum):
        yes = "Yes"
        no = "No"
    
    hostname: Optional[str]
    hostlocation: HostLocation
    company: Company
    built: Optional[datetime.date]
    lastrenovated: Optional[datetime.date]
    rentedSince: Optional[datetime.date]
    host_pic_url: Optional[str]
    welcome_msg: Optional[str]
    owner_listing_story: Optional[str]
    neighborhood_overview: Optional[str]
    local_tips: Optional[str]

class InvoicesContact(BaseModel):
    firstname: Optional[str]
    lastname: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    postcode: Optional[str]

class ReservationsContact(BaseModel):
    firstname: Optional[str]
    lastname: Optional[str]
    email: Optional[str]
    phone: Optional[str]

class Policies(BaseModel):
    policies: list[str]

    
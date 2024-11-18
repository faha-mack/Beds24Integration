from typing import Literal, Optional
from pydantic import BaseModel

class ListingDetails(BaseModel):
    publish: Literal['yes', 'no']
    proptypegroup: Literal['', 'apartments', 'bnb', 'boutique_hotels_and_more', 
                            'houses', 'secondary_units', 'unique_homes']
    listingtype: Literal['private_room', 'shared_room', 'entire_home']
    hideaddress: Literal[0, 1]
    picsource: Literal['rop', 'ro', 'rp', 'r', 'p']
    bathroomshared: Literal['', 'private', 'host', 'family_friends_roommates', 
                            'other_guests', 'host,family_friends_roommates', 
                            'host,other_guests', 'family_friends_roommates,other_guests', 
                            'host,family_friends_roommates,other_guests']
    commonshared: Literal['', 'private', 'host', 'family_friends_roommates', 
                          'other_guests', 'host,family_friends_roommates', 
                          'host,other_guests', 'family_friends_roommates,other_guests', 
                          'host,family_friends_roommates,other_guests']
    checkincategory: Literal['host_checkin', 'doorman_entry', 'keypad', 'lockbox', 
                             'other_checkin', 'smartlock']
    checkindesc: Optional[str]
    housemanual: Optional[str]
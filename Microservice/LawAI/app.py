from flask import Flask, jsonify, request, send_file
from prometheus_flask_exporter import PrometheusMetrics
import google.generativeai as genai
from docx import Document
import requests
import io
from flask_cors import CORS
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST



app = Flask(__name__)
# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, defaults_prefix='my_app')

# Enable CORS for all routes
CORS(app)


@app.route('/metrics')
def metrics_route():

    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

class GeminiAI:
    def __init__(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=self.api_key)

    def generate_response(self, prompt):
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error occurred: {e}"

@app.route('/v1/law', methods=['POST'])
def lawai():
    print("1 ------------ Received query")

    # Get the user input from the request
    data = request.get_json()
    query = data.get('query', '')
    print("2 ------------ Processing query")
    chat_prompt = (
    f"You are a legal document classifier. Your task is to identify the type of legal document based on the query provided. "
    f"There are only three valid document types: 'rental', 'adoption', and 'sale deed'. "
    f"Follow these rules strictly: "
    f"1. If the document matches one of the three types, respond in JSON format as follows: {{\"document\": \"<type>\"}}, where <type> is 'rental', 'adoption', or 'sale deed'. "
    f"2. If the document does not match any of the three types, respond strictly as: {{\"document\": \"False\"}}. "
    f"3. Do not include any additional words, explanations, or formatting such as ```json```. "
    f"Only return the exact JSON response as specified. "
    f"Here is the query: {query}"
)


    # Configure Gemini AI
    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("3 ------------ Sending classification prompt")

    # Get the classification response
    response = gemini_client.generate_response(chat_prompt)
    print(f"4 ------------ Classification response: {response}")

    try:
        # Parse the response
        response_data = eval(response)  # Assuming the response is in JSON-like format (e.g., {'document': 'rental'})
        document_type = response_data.get('document')

        # Handle the classification result
        if document_type == 'rental':
            print("5 ------------ Document identified as rental, calling rentalai function")
            return rentalai()
        elif document_type == 'False':
            print("6 ------------ Invalid document type")
            return jsonify({"error": "Invalid document type. Please provide a valid query."})
        else:
            print(f"7 ------------ Document type not supported: {document_type}")
            return jsonify({"error": f"Unsupported document type: {document_type}"})
    except Exception as e:
        print(f"8 ------------ Error occurred while processing response: {e}")
        return jsonify({"error": f"Error occurred: {e}"})

def rentalai():
    print("1 ------------ question")

    data = request.get_json()
    query = data.get('query', '')
    print("3 ------------ question")

    chat_prompt = (
     """
        RESIDENTIAL RENTAL AGREEMENT
        This agreement made at #city, #state on this #ddmmyy between #landlordname, residing at #landlordaddress1, #lordaddressline2, #lordcity, #lordstate, #lordpincode hereinafter referred to as the `LESSOR` of the One Part AND #tenantname, residing at  #tenantaddress1, #tenantaddressline2, #tencity, #tenstate, #tenpincode hereinafter referred to as the `LESSEE` of the other Part;
        WHEREAS the Lessor is the lawful owner of, and otherwise well sufficiently entitled to #leasepropertyaddress1, #leaseaddressline2, #leasecity, #leasestate, #leasepincode falling in the category, #independenthouse / #apartment / #farmhouse / #residentialproperty and comprising of #xbedrooms, #xbathrooms, #xcarparks with an extent of #xxxxsquarefeet hereinafter referred to as the `said premises`. 
        AND WHEREAS at the request of the Lessee, the Lessor has agreed to let the said premises to the tenant for a term of #leaseterm commencing from #leasestartdate in the manner hereinafter appearing. 

        NOW THIS AGREEMENT WITNESSETH AND IT IS HEREBY AGREED BY AND BETWEEN THE PARTIES AS UNDER:
        1.	That the Lessor hereby grants to the Lessee, the right to enter into use and remain in the said premises along with the existing fixtures and fittings listed in Annexure 1 to this Agreement and that the Lessee shall be entitled to peacefully possess, and enjoy possession of the said premises, and the other rights herein.
        2.	That the lease hereby granted shall, unless cancelled earlier under any provision of this Agreement, remain in force for a period of #leaseterm. 
        3.	That the Lessee will have the option to terminate this lease by giving #onemonthnotice in writing to the Lessor.
        4.	That the Lessee shall have no right to create any sub-lease or assign or transfer in any manner the lease or give to anyone the possession of the said premises or any part thereof.
        5.	That the Lessee shall use the said premises only for residential purposes.
        6.	That the Lessor shall, before handing over the said premises, ensure the working of sanitary, electrical and water supply connections and other fittings pertaining to the said premises. It is agreed that it shall be the responsibility of the Lessor for their return in the working condition at the time of re-possession of the said premises (reasonable wear and tear and loss or damage by fire, flood, rains, accident, irresistible force or act of God excepted).
        7.	That the Lessee is not authorized to make any alteration in the construction of the said premises. The Lessee may however install and remove his own fittings and fixtures, provided this is done without causing any excessive damage or loss to the said premises.
        8.	That the day-to-day repair jobs such as fuse blow out, replacement of light bulbs/tubes, leakage of water taps, maintenance of the water pump and other minor repairs, etc., shall be effected by the Lessee at its own cost, and any major repairs, either structural or to the electrical or water connection, plumbing leaks, water seepage shall be attended to by the Lessor. In the event of the Lessor failing to carry out the repairs on receiving notice from the Lessee, the Lessee shall undertake the necessary repairs and the Lessor will be liable to immediately reimburse costs incurred by the Lessee.
        9.	That the Lessor or its duly authorized agent shall have the right to enter into or upon the said premises or any part thereof at a mutually arranged convenient time for the purpose of inspection. 
        10.	That the Lessee shall use the said premises along with its fixtures and fitting in careful and responsible manner and shall handover the premises to the Lessor in working condition (reasonable wear and tear and loss or damage by fire, flood, rains, accidents, irresistible force or act of God excepted).
        11.	That in consideration of use of the said premises the Lessee agrees that he shall pay to the Lessor during the period of this agreement, a monthly rent at the rate of #monthlyrentalinnumber&words. The amount will be paid in advance on or before the date of #paiday of every English calendar month.
        12.	It is hereby agreed that if default is made by the lessee in payment of the rent for a period of three months, or in observance and performance of any of the covenants and stipulations hereby contained and on the part to be observed and performed by the lessee, then on such default, the lessor shall be entitled in addition to or in the alternative to any other remedy that may be available to him at this discretion, to terminate the lease and eject the lessee from the said premises; and to take possession thereof as full and absolute owner thereof, provided that a notice in writing shall be given by the lessor to the lessee of his intention to terminate the lease and to take possession of the said premises. If the arrears of rent are paid or the lessee comply with or carry out the covenants and conditions or stipulations, within fifteen days from the service of such notice, then the lessor shall not be entitled to take possession of the said premises.
        13.	That in addition to the compensation mentioned above, the Lessee shall pay the actual electricity, shared maintenance, water bills for the period of the agreement directly to the authorities concerned. The relevant `start date` meter readings are #startingmetereading. 
        14.	That the Lessee has paid to the Lessor a sum of #rentaldepositinumber&words as deposit, free of interest, which the Lessor does accept and acknowledge. This deposit is for the due performance and observance of the terms and conditions of this Agreement. The deposit shall be returned to the Lessee simultaneously with the Lessee vacating the said premises. In the event of failure on the part of the Lessor to refund the said deposit amount to the Lessee as aforesaid, the Lessee shall be entitled to continue to use and occupy the said premises without payment of any rent until the Lessor refunds the said amount (without prejudice to the Lessee`s rights and remedies in law to recover the deposit).
        15.	That the Lessor shall be responsible for the payment of all taxes and levies pertaining to the said premises including but not limited to House Tax, Property Tax, other cesses, if any, and any other statutory taxes, levied by the Government or Governmental Departments. During the term of this Agreement, the Lessor shall comply with all rules, regulations and requirements of any statutory authority, local, state and central government and governmental departments in relation to the said premises.
        IN WITNESS WHEREOF, the parties hereto have set their hands on the day and year first hereinabove mentioned. 

        Lessor,	Lessee,
        #name	#name
        # landlordaddress1	# tenantaddress1
        #lordaddressline2	#tenantaddressline2
        #lordcity, #lordstate, #lordpincode	#tencity, #tenstate, #tenpincode


        WITNESS ONE	WITNESS TWO


        [Name & Address]	[Name & Address]

        ANNEXURE I
        List of fixtures and fittings provided in #leasepropertyaddress1, #leaseaddressline2, #leasecity, #leasestate, #leasepincode: 
        1.	#item1
        2.	#item2
        3.	#item3
        """
        f"You are an assistant tasked with filling out a Residential Rental Agreement based on the user's query. The agreement contains placeholders that need to be replaced with specific details from the user's input. The placeholders are as in #city like this, itll start with a # so you need to replace those fileds only and return the full aggremmentYour task is to process the following user query and extract the required information to replace the placeholders in the agreement accordingly. If any field s missing raise a question to user about please provide that specific field The query is: {query}"
)

    print("6 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("7 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("8 ------------ question")
    if isinstance(response, str):

        points = response.split('\n')  # Split by new lines or you can use regex for better splitting
        # Clean up each point (remove extra spaces)
        points = [point.strip() for point in points if point.strip()]

    return jsonify({"answer": points})



@app.route('/v1/sale', methods=['POST'])
def saleai():
    print("1 ------------ question")

    data = request.get_json()
    query = data.get('query', '')
    print("3 ------------ question")

    chat_prompt = (
     """SALE DEED
        THIS DEED OF ABSOLUTE SALE IS EXECUTED AT CHENNAI ON THIS THE #datend  DAY OF #month #year BY:-
        #vendorname, S/o. Mr. #vendorfathername, #vendorreligion, aged about #vendorage years, residing at #vendoraddress. (Aadhaar No: #vendoraadharnumber) [PAN No: #vendorpannumber) hereinafter called as the "VENDOR" which terms shall mean and include his legal representatives, heirs, assigns and nominees. 

        AND
        #purchasername, S/o. Mr. #purchaserfathername, #purchaserreligion, aged about #purchaserage years, residing at #purchaseraddress. (Aadhaar No: #purchaseraadharnumber) (PAN No: #purchaserpannumber), hereinafter called as the "PURCHASER" which term shall mean and include his respective heirs, legal representatives, executors and assigns.



        WHEREAS, the VENDOR is the owner of #propertydetails
        WHEREAS, the VENDOR is thus in absolute possession and enjoyment of the schedule property ever since the date of purchase which is free from encumbrances and his possession and enjoyment are evident from the records issued by the Government authorities.
        WHEREAS except an equitable mortgage by Deposit of Title Deeds with M/s.Housing Development Finance Corporation Ltd. in Loan Account No. #ownerloanaccountnumber the outstanding sum payable towards the same being Rs.#loansumnumbers/- (Rupees #loansumwords), there are no other encumbrance such as any other mortgage, hypothecation, attachment or any claim of whatsoever nature over the property morefully described in Schedule hereunder.

        WHEREAS the VENDOR who is in need of funds for the purpose of settling his liabilities, has decided to sell the property more fully described in the Schedule hereunder and the PURCHASER has offered to purchase the same for a total sale consideration of Rs.#saleamountnumbers/- (Rupees #saleamountwords Only) from the VENDOR more fully described in Schedule hereunder free from all encumbrances.



        WHEREAS the VENDOR has offered to sell the #propertytobesold comprised in S.No.#propertyoldnumber Part and New S.No.#propertynewnumber as per patta no.#propertypattanumber situated at #propertyaddress, measuring an area of #propertyarea sq.ft #otherpropertiesforsale, for a total Sale consideration of Rs.#saleamountnumbers/- (Rupees #saleamountwords Only) free from all encumbrances, which offer has been accepted by the PURCHASER.
        NOW THIS DEED OF ABSOLUTE SALE WITNESSETH: -

        Pursuant to the above said recitals and in consideration of the PURCHASER having paid a sum of Rs.#saleamountnumbers/- (Rupees #saleamountwords Only) to the VENDOR in the following manner: -

        1. A sum of Rs.#sumadvance1/- is paid as advance by way of #sum1mode1 dated #sum1mode1date bearing No.#sum1mode1number drawn on #sum1mode1bankname Bank, #sum1mode1bankbranch, in favour of the VENDOR.
        2. Further payment of Rs.#sumadvance2/- is transferred by way of #sum2mode2 Transaction from the SB Account No.#sum2mode2number, #sum2mode2bankname Bank, #sum2mode2bankbranch to the VENDOR's account at #vendorbankname, #vendorbankbranch, bearing SB Account No. #vendorbanknumber.

        3. Further payment of Rs.#sumadvance3/- is paid by  Purchaser by way of #sum3mode3 bearing #sum3mode3number drawn on #sum3mode3bankname, #sum3mode3bankbranch, in favour of the VENDOR.
            
        4. #furtherpaymentdetails
        in all a total sum of Rs.#saleamountnumbers/- (Rupees #saleamountwords Only), the receipt of which sum in full the Vendor doth hereby admit and  acknowledge and hereby release the PURCHASER from any further payment thereof and the Vendor doth hereby convey, sell, grant and transfer to and unto the PURCHASER the said schedule mentioned property, more fully described in the schedule hereunder with all the rights, title and interest of the Vendor of the said property TO HAVE AND TO HOLD the same as absolute owner thereof, together with all easements, privileges or other benefits attached to the said land and enjoyed therewith.
        THE VENDOR doth hereby declare and covenant with the PURCHASER that there are no encumbrances on the said schedule mentioned property and it is not subject matter of any suit, litigation or proceedings and there are no encumbrances, charges, liens, trusts, attachments, claims or demands, will or attachment, maintenance charges, whatsoever now subsisting on the said schedule mentioned property and it has not been offered or given as security or mortgage by any court, tribunal or revenue or other authorities.

        THE VENDOR doth hereby declare and covenant with the PURCHASER that the Vendor shall and will at all times indemnify the PURCHASER against all claims and demands whatsoever in respect of the said schedule mentioned property and make good to the PURCHASER all losses, damages, costs and expenses which the PURCHASER may be put to, incur or suffer by reasons of any defect, deficiency in the title of the vendor to the property.

        THE VENDOR doth hereby declare and covenant with the PURCHASER that he has put the PURCHASER in vacant possession of the said schedule mentioned property and the PURCHASER shall and may peacefully and quietly enter into, possess and enjoy the schedule mentioned property without any let or hindrance, interruption or disturbances from any other person lawfully claiming through or under him.

        THE VENDOR doth hereby declare and covenant with the PURCHASER that he has paid all taxes due to the government till this day and all other taxes levied hereafter shall be borne by the PURCHASER only. 
        THE VENDOR doth hereby agree and undertake to execute further deed or deeds as may be reasonably required to assure better and perfect title to the PURCHASER.
        THE VENDOR further covenants with the PURCHASER that the Vendor shall at all times execute, register or cause to be done, executed and registered at the expense of the PURCHASER all such further acts or acts, deeds and things which the PURCHASER may reasonably require for more effectively assuring the title of the schedule property to the PURCHASER.
        The VENDOR has put the PURCHASER in physical possession of the schedule mentioned property from this date.
        THE PURCHASER can apply for mutation of records in his name in the Revenue Patta as regards his undivided share in the schedule mentioned property and as well mutate his name with the property register kept with the Corporation of Chennai and CMWSSB and also the electricity service connection with TNEB.
        THE VENDOR has on this day delivered all the original documents and other relevant documents relating to the schedule mentioned property to the PURCHASER.
        SCHEDULE
        All that piece and parcel of #propertydetails and the Plot is bounded on the: -
        NORTH BY	: Plot No.21	
        SOUTH BY   : Plot No.23
        EAST BY  	: 30 Feet wide road	
        WEST BY	: Plot No.29	

        Admeasuring
        #directionalmeasurementsinfeet
        together with a #propertydetails


        The Market value of the above said property is Rs.#saleamountnumbers/- and stamp duty is paid accordingly.
        IN WITNESS WHEREOF THE VENDOR AND THE PURCHASER HAVE PUT THEIR RESPECTIVE SIGNATURES ON THE DAY, MONTH AND YEAR FIRST ABOVE WRITTEN BEFORE THE WITNESSES

        VENDOR                                                                                     PURCHASER

        WITNESSES: 
        #witness1name


        #witness2name
        """
        f"You are an assistant tasked with filling out a SALE DEED  based on the user's query. The agreement contains placeholders that need to be replaced with specific details from the user's input. The placeholders are as in #city like this, itll start with a # so you need to replace those fileds only and return the full aggremmentYour task is to process the following user query and extract the required information to replace the placeholders in the agreement accordingly. If any field s missing raise a question to user about please provide that specific field The query is: {query}"
)

    print("6 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("7 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("8 ------------ question")
    if isinstance(response, str):

        points = response.split('\n')  # Split by new lines or you can use regex for better splitting
        # Clean up each point (remove extra spaces)
        points = [point.strip() for point in points if point.strip()]

    return jsonify({"answer": points})



@app.route('/v1/adoption', methods=['POST'])
def adoptionai():
    print("1 ------------ question")

    data = request.get_json()
    query = data.get('query', '')
    print("3 ------------ question")

    chat_prompt = (
     """In the High Court of Judicature at #courtvenue
        (Ordinary Original Civil Jurisdiction)
        O.P. NO. #casenumber OF #caseyear
        (In the matter of Juvenile Justice (Care and Protection of Children) Act, 2015 and 
        (In the matter of Minor child #childname, born on #childdob, 
        #childgender, #childreligion)
        #petitionerfathername
        Son of #petitionerparentnameoffather
        #petitionermothername
        Wife of #petitionerfathername

        Both residing at 
        #petitioneraddress                                                                     	…Petitioners
        -Versus-
        #respondentfathername
        Son of #respondentparentnameoffather
        G. Dhanalakshmi
        Wife of #respondentfathername

        Both residing at 
        #respondentaddress                                        	                              …Respondents

        Petition under sec. 56(2) of the Juvenile Justice (Care and Protection of Children) Act 2015 (as amended by Act 2 of 2016)

        The above named Petitioners respectfully state as follows:
        The First Petitioner is #petitionerfathername Son of #petitionerparentnameoffather, Indian #petitioner1religion, aged about #petitioner1age years, #petitioneraddress.
        The Second Petitioner is #petitionermothername Wife of #petitionerfathername, Indian #petitioner2religion, aged about #petitioner2age years, #petitioneraddress.
        The Address for service of all notices and processes on the Petitioners is that of their counsel #advocatename (#advocateenrollment) Advocate, having their office at #advocateoffice (Mobile: #advocatenumber).
        The First Respondent is #respondentfathername Son of #respondentparentnameoffather, #respondent1religion, aged about #respondent1age years, residing at #respondentaddress.                                                                     …2…
        -2-
        The Second Respondent is #respondentmothername Wife of #respondentfathername, #respondent2religion, aged about #respondent2age years, residing at #respondentaddress.
        The Address for service of all notices and processes on the Respondents is as same as stated above.
        The First Petitioner and the Second Petitioner are the husband and wife.  Likewise the First Respondent and the Second Respondent are the husband and wife.
        The Respondents gave birth of a #childgender child out of their legal wedlock on #respondentmarriagedate and christened the said #childgender child as "#childname".  The said minor #childgender child was born at #childhospitaladdress and the same was registered in Registration No.#childregistrationnumber dated #registrationdate, on the file of Corporation of Greater Chennai.  A Birth Certificate has been issued by the City Health Officer (i/c), Greater Chennai Corporation to that effect.
        The Petitioners have no children and the possibility of them having any children in future does not exist given their age and medical history.
        The Petitioners are desirous of adopting a child and approached the Respondents herein seeking to adopt their minor #childgender child "#childname" as their daughter.
        The Respondents, taking into consideration of the friendship between the Petitioners and the Respondents had consented and expressed their agreement to give their minor #childgender child "#childname" in adoption to the Petitioners herein.
        The Respondents herein had handed over the minor #childgender child "#childname" to the Petitioners on #handoverdate and the Petitioners had also adopted the said minor #childgender child in the presence of witnesses, friends and relatives.
        The Petitioners and the Respondents herein had entered into an Adoption Deed dated #adoptiondate to that effect and through which the Respondents herein had admitted, accepted and acknowledged the Adoption of Minor #childgender Child "#childname" by the Petitioners herein.  Thus the Minor #childgender Child "#childname" was handed over by the Respondents herein to the Petitioners herein and the Petitioners herein had adopted the Minor #childgender Child "#childname" on #adoptiondate and taken care of the said Minor #childgender Child from that day onwards.
        The Petitioners are wealthy and have sufficient source of income and properties, both movables and immovable to take care of the adopted minor child "#childname" in a good manner.                                                      …3… 
        -3-
        The paramount welfare of the adopted child "#childname" will be well considered by the Petitioners herein.  The Petitioners are Indian Christians and the Respondents are Hindus and the Petitioners are having capacity to adopt the child and they are willing to take the child on adoptions.  They are having sufficient means to bring up and maintain the minor #childgender child "#childname".  They are having every means to give proper and high education and favorable upbringing with the full right of succession and inheritance.
        The Respondents state that the Adoption is only for the welfare of the Minor #childgender Child "#childname" for which they have not received any payment or any consideration.  From the birth of the said Minor #childgender Child "#childname", the Petitioners are nurturing the said Minor #childgender Child "#childname" as the guardian of the child.
        The Petitioners state that the said Minor #childgender Child "#childname" is with the Petitioners from the date of adoption of the said child viz., #adoptiondate and the Petitioners are very affectionate and cordial towards the child and vice versa.  The child is also very much attached with them and moves with them as father and mother.  From the date of Adoption i.e., #adoptiondate, the Petitioners had been bringing up the said minor #childgender child "#childname", as their own bestowing the parental affection.
        The Petitioners state that they are hale and healthy and do not suffer any diseases or infirmity.  Further to that, the parents of the said minor #childgender child #childname, the Respondents herein had already expressed their willingness to  give adoption of the minor #childgender child "#childname" to the petitioners and executed a Deed of Adoption dated #adoptiondate to that effect.
        The Petitioners state that they do not have any adverse interest against the minor #childgender child "#childname".
        The Petitioners state that the minor #childgender child "#childname" has not been adopted by any court.  The Petitioners state that the said minor #childgender Child "#childname" does not possess any property in her name.
        The Petitioners state that they required Adoption through Court of Law as all Schools and other Educational Institutions, Banks and other Financial Institutions, Government officials & Departments, Passport Authorities demanded Adoption through Court of Law and for which these Petitioners have no other option but to approach this Hon'ble Court for the same.  
        The Petitioners state that the cause of action for the petition to seeking permission for adoptions arose at Chennai on #permissiondate, when the minor #childgender child " #childname" born at #childhospitaladdress to the Respondents herein and on #adoptiondate, when the
        …4…
        -4-
        Petitioners and the Respondents entered into a Deed of Adoption and thereby confirming the Adoption given by the Respondents to the Petitioners and admitting, accepting & acknowledging the Adoption by the Petitioners from the date of adoption of minor #childgender child "#childname" viz., #adoptiondate and, when the Petitioners adopted the above said minor #childgender child "#childname" from the Respondents and nurture the child as guardian and on all these days commencing from #residingdate, when the child is living with the Petitioners at #petitioneraddress from the date of adoption i.e., #adoptiondate and still living thereon as on date and subsequently, all falls within the jurisdiction of this Hon'ble Court.
        The Petitioners state that this Hon'ble Court has jurisdiction to entertain the Petition since the above said minor #childgender child "#childname" resides at #petitioneraddress with the Petitioners from #residingdate, which falls within the jurisdiction of this Hon'ble Court.
        The Petitioners pay a court fee of Rs.50/- under Article 11(l), Schedule - II of Tamil Nadu Court Fees and Suit Valuation Act, 1955.
        The Petitioners respectfully pray that this Hon'ble court may be pleased to:-
        Appoint the Petitioners as Parents of the person of the minor #childgender child "#childname" born on #permissiondate; and 
        That the said minor #childgender child "#childname" shall be entitled for all the legal rights including the right of inheritance and succession as a natural born biological child shall have and render justice.
        Dated at #place on this #todaydate
        1)

        2)
        Counsel for Petitioners.                                                                     Petitioners
        VERIFICATION
        We (1) #petitionerfathername (2) #petitionermothername, the Petitioners herein do hereby verify that what has been stated above Paragraphs 1 to 25 are true and correct to the best of our knowledge and belief and nothing has been concealed.
        Verified at #place on this #datetoday
        1)

        2)
        Petitioners
        …5…
        -5-
        LIST OF DOCUMENTS FILED ALONG WITH THIS PETITION:-
        Voter Identity Card of the First Petitioner (Xerox).
        Family Card of the Petitioners 2005 - 2009 (Xerox)
        Aadhar Card of the First Petitioner (Xerox)
        Aadhar Card of the Second Petitioner (Xerox)
        Birth Certificate of the minor #childgender child "#childname" dated #childdob (Computer Generated Copy) 
        Deed of Adoption entered between the Petitioners and the Respondents dated #adoptiondate (Original)
        Dated at #place on this #datetoday



        Counsel for petitioners




        """
        f"You are an assistant tasked with filling out a Adoption based on the user's query. The agreement contains placeholders that need to be replaced with specific details from the user's input. The placeholders are as in #city like this, itll start with a # so you need to replace those fileds only and return the full aggremmentYour task is to process the following user query and extract the required information to replace the placeholders in the agreement accordingly. If any field s missing raise a question to user about please provide that specific field The query is: {query}"
)

    print("6 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("7 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("8 ------------ question")
    if isinstance(response, str):

        points = response.split('\n')  # Split by new lines or you can use regex for better splitting
        points = [point.strip() for point in points if point.strip()]

    return jsonify({"answer": points})

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5003)
